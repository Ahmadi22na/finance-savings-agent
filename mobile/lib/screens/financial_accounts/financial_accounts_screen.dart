import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/account_format.dart';
import '../../core/api_client.dart';
import '../../core/financial_account_providers.dart';
import '../../core/providers.dart';
import '../../models/financial_account.dart';
import '../../theme/app_theme.dart';
import '../../widgets/account_balance_sheet.dart';
import '../../widgets/account_snapshots_sheet.dart';
import '../../widgets/financial_account_form_sheet.dart';
import '../../widgets/transaction_tile.dart';

String _messageOf(Object error) => error is ApiException ? error.message : 'صار خطأ غير متوقع، جرب كمان شوي';

IconData _kindIcon(String kind) {
  switch (kind) {
    case 'bank':
      return Icons.account_balance_outlined;
    case 'wallet':
      return Icons.account_balance_wallet_outlined;
    case 'cash':
    default:
      return Icons.payments_outlined;
  }
}

enum _AccountAction { updateBalance, edit, snapshots, archive, reactivate, delete }

/// شاشة "حساباتي المالية": حسابات يدوية (كاش/بنك/محفظة) بأرصدة بتدخلها إنت. اختيارية بالكامل، وما فيها أي ربط بنكي.
/// كل الأرقام (الرصيد، جودته، المجموع، incomplete) جاية من السيرفر؛ الواجهة بتعرضها وبس.
class FinancialAccountsScreen extends ConsumerWidget {
  const FinancialAccountsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final accountsAsync = ref.watch(financialAccountsProvider);
    final showArchived = ref.watch(showArchivedAccountsProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('حساباتي المالية')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _addAccount(context, ref),
        icon: const Icon(Icons.add),
        label: const Text('حساب جديد'),
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          refreshFinancialAccounts(ref);
          try {
            await ref.read(financialAccountsProvider.future);
          } catch (_) {
            // الخطأ بيظهر بالقائمة نفسها مع زر إعادة المحاولة
          }
        },
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
          children: [
            const _SummaryCard(),
            const SizedBox(height: 8),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('عرض الحسابات المؤرشفة'),
              value: showArchived,
              onChanged: (value) => ref.read(showArchivedAccountsProvider.notifier).state = value,
            ),
            ...accountsAsync.when(
              loading: () => [
                const Padding(padding: EdgeInsets.all(32), child: Center(child: CircularProgressIndicator())),
              ],
              error: (error, _) => [
                _ErrorBox(message: _messageOf(error), onRetry: () => ref.invalidate(financialAccountsProvider)),
              ],
              data: (accounts) => accounts.isEmpty
                  ? [_EmptyState(onAdd: () => _addAccount(context, ref))]
                  : [
                      for (final account in accounts)
                        _AccountCard(account: account, onTap: () => _openActions(context, ref, account)),
                    ],
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _addAccount(BuildContext context, WidgetRef ref) async {
    final saved = await showFinancialAccountFormSheet(context);
    if (saved == true) {
      refreshFinancialAccounts(ref);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('تمت إضافة الحساب ✅')));
      }
    }
  }

  Future<void> _openActions(BuildContext context, WidgetRef ref, FinancialAccount account) async {
    final action = await showModalBottomSheet<_AccountAction>(
      context: context,
      showDragHandle: true,
      builder: (_) => _ActionsSheet(account: account),
    );
    if (action == null || !context.mounted) return;

    switch (action) {
      case _AccountAction.updateBalance:
        final saved = await showAccountBalanceSheet(context, account);
        if (saved == true) {
          refreshFinancialAccounts(ref);
          if (context.mounted) {
            ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('تم تسجيل الرصيد ✅')));
          }
        }
        break;
      case _AccountAction.edit:
        final saved = await showFinancialAccountFormSheet(context, existing: account);
        if (saved == true) {
          refreshFinancialAccounts(ref);
          if (context.mounted) {
            ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('تم تعديل الحساب ✅')));
          }
        }
        break;
      case _AccountAction.snapshots:
        await showAccountSnapshotsSheet(context, account);
        break;
      case _AccountAction.archive:
        await _archive(context, ref, account);
        break;
      case _AccountAction.reactivate:
        await _run(context, ref, () => ref.read(financialAccountServiceProvider).updateAccount(account.id, isActive: true),
            'تمت إعادة تفعيل الحساب ✅');
        break;
      case _AccountAction.delete:
        await _delete(context, ref, account);
        break;
    }
  }

  /// بينفّذ طلبًا ويعرض نتيجته برسالة واضحة. بيرجّع true لو نجح.
  Future<bool> _run(BuildContext context, WidgetRef ref, Future<Object?> Function() action, String success) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      await action();
      refreshFinancialAccounts(ref);
      messenger.showSnackBar(SnackBar(content: Text(success)));
      return true;
    } on ApiException catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(e.message)));
    } catch (_) {
      messenger.showSnackBar(const SnackBar(content: Text('صار خطأ غير متوقع، جرب كمان شوي')));
    }
    return false;
  }

  Future<void> _archive(BuildContext context, WidgetRef ref, FinancialAccount account) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('أرشفة الحساب؟'),
        content: Text(
          'حساب "${account.name}" رح يختفي من القائمة وما بيستقبل معاملات أو أرصدة جديدة. سجله بيضل محفوظ '
          'وبتقدر تعرضه وتعيد تفعيله بأي وقت.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(false), child: const Text('إلغاء')),
          FilledButton(onPressed: () => Navigator.of(dialogContext).pop(true), child: const Text('أرشف')),
        ],
      ),
    );
    if (confirmed != true || !context.mounted) return;
    await _run(context, ref, () => ref.read(financialAccountServiceProvider).updateAccount(account.id, isActive: false),
        'تمت أرشفة الحساب');
  }

  /// الحذف بيقرره السيرفر: لو رفض بـ 409 (عليه معاملات أو أرصدة)، بنعرض رسالته مع خيار الأرشفة بدل الحذف.
  Future<void> _delete(BuildContext context, WidgetRef ref, FinancialAccount account) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('حذف الحساب؟'),
        content: Text(
          'رح يتحذف حساب "${account.name}" نهائيًا. إذا عليه معاملات أو أرصدة مسجّلة ما رح يتحذف، '
          'وبتقدر تأرشفه بدل الحذف.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(false), child: const Text('إلغاء')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: TransactionTile.expenseColor),
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('احذف'),
          ),
        ],
      ),
    );
    if (confirmed != true || !context.mounted) return;

    final messenger = ScaffoldMessenger.of(context);
    try {
      await ref.read(financialAccountServiceProvider).deleteAccount(account.id);
      refreshFinancialAccounts(ref);
      messenger.showSnackBar(const SnackBar(content: Text('تم حذف الحساب')));
    } on ApiException catch (e) {
      if (e.statusCode == 409 && context.mounted) {
        await _offerArchiveInstead(context, ref, account, e.message);
      } else {
        messenger.showSnackBar(SnackBar(content: Text(e.message)));
      }
    } catch (_) {
      messenger.showSnackBar(const SnackBar(content: Text('صار خطأ غير متوقع، جرب كمان شوي')));
    }
  }

  Future<void> _offerArchiveInstead(
      BuildContext context, WidgetRef ref, FinancialAccount account, String serverMessage) async {
    final archive = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('ما قدرنا نحذف الحساب'),
        content: Text(serverMessage),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(false), child: const Text('إلغاء')),
          FilledButton(onPressed: () => Navigator.of(dialogContext).pop(true), child: const Text('أرشف بدل الحذف')),
        ],
      ),
    );
    if (archive != true || !context.mounted) return;
    await _run(context, ref, () => ref.read(financialAccountServiceProvider).updateAccount(account.id, isActive: false),
        'تمت أرشفة الحساب');
  }
}

class _ActionsSheet extends StatelessWidget {
  final FinancialAccount account;

  const _ActionsSheet({required this.account});

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: Icon(_kindIcon(account.kind)),
              title: Text(account.name, maxLines: 1, overflow: TextOverflow.ellipsis),
              subtitle: Text(account.isActive ? accountKindLabel(account.kind) : '${accountKindLabel(account.kind)} • مؤرشف'),
            ),
            const Divider(height: 1),
            ListTile(
              leading: const Icon(Icons.edit_note_outlined),
              title: const Text('تحديث الرصيد'),
              subtitle: account.isActive ? null : const Text('الحساب مؤرشف: أعد تفعيله أولاً'),
              enabled: account.isActive,
              onTap: () => Navigator.of(context).pop(_AccountAction.updateBalance),
            ),
            ListTile(
              leading: const Icon(Icons.drive_file_rename_outline),
              title: const Text('تعديل الاسم والنوع'),
              onTap: () => Navigator.of(context).pop(_AccountAction.edit),
            ),
            ListTile(
              leading: const Icon(Icons.history),
              title: const Text('سجل الأرصدة (للمراجعة)'),
              onTap: () => Navigator.of(context).pop(_AccountAction.snapshots),
            ),
            if (account.isActive)
              ListTile(
                leading: const Icon(Icons.archive_outlined),
                title: const Text('أرشفة الحساب'),
                onTap: () => Navigator.of(context).pop(_AccountAction.archive),
              )
            else
              ListTile(
                leading: const Icon(Icons.unarchive_outlined),
                title: const Text('إعادة تفعيل الحساب'),
                onTap: () => Navigator.of(context).pop(_AccountAction.reactivate),
              ),
            ListTile(
              leading: const Icon(Icons.delete_outline, color: TransactionTile.expenseColor),
              title: const Text('حذف الحساب', style: TextStyle(color: TransactionTile.expenseColor)),
              onTap: () => Navigator.of(context).pop(_AccountAction.delete),
            ),
          ],
        ),
      ),
    );
  }
}

/// ملاحظة تحذيرية بنص وأيقونة (مش بلون وحده).
class _Notice extends StatelessWidget {
  final String text;

  const _Notice(this.text);

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: TransactionTile.uncategorizedBadgeBackground,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.info_outline, size: 18, color: TransactionTile.uncategorizedBadgeForeground),
          const SizedBox(width: 8),
          Expanded(
            child: Text(text, style: const TextStyle(fontSize: 13, color: TransactionTile.uncategorizedBadgeForeground)),
          ),
        ],
      ),
    );
  }
}

class _SummaryCard extends ConsumerWidget {
  const _SummaryCard();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final summaryAsync = ref.watch(accountsSummaryProvider);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: summaryAsync.when(
          loading: () => const SizedBox(height: 64, child: Center(child: CircularProgressIndicator())),
          error: (error, _) => _ErrorBox(
            message: _messageOf(error),
            onRetry: () => ref.invalidate(accountsSummaryProvider),
          ),
          data: (summary) {
            final partial = summary.incomplete && summary.total != null;
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(partial ? 'المجموع الجزئي (غير كامل)' : 'مجموع حساباتك المفعّلة',
                    style: const TextStyle(fontSize: 13, color: AppColors.secondaryText)),
                const SizedBox(height: 4),
                // الرصيد المجهول مش صفر: لو ما في مجموع بنقول "غير معروف"
                Text(
                  summary.total == null ? 'غير معروف' : '${formatMoney(summary.total!)} دينار',
                  style: const TextStyle(fontSize: 26, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 4),
                Text(
                  summary.accountsTotal == 0
                      ? 'ما عندك حسابات مفعّلة'
                      : 'محسوب من ${summary.accountsCounted} من أصل ${summary.accountsTotal} حساب',
                  style: const TextStyle(fontSize: 13, color: AppColors.secondaryText),
                ),
                if (summary.incomplete) ...[
                  const SizedBox(height: 10),
                  _Notice([
                    if (summary.hasUnknown) 'في حساب ما سجّلت رصيده لسا.',
                    if (summary.hasStale) 'في رصيد قديم ويحتاج تحديث.',
                    'لا تعتبر هالرقم مؤكد.',
                  ].join(' ')),
                ],
              ],
            );
          },
        ),
      ),
    );
  }
}

class _AccountCard extends StatelessWidget {
  final FinancialAccount account;
  final VoidCallback onTap;

  const _AccountCard({required this.account, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(_kindIcon(account.kind), size: 20),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(account.name,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                  ),
                  Text(accountKindLabel(account.kind), style: const TextStyle(fontSize: 12, color: AppColors.secondaryText)),
                  if (!account.isActive) ...[
                    const SizedBox(width: 8),
                    const _Pill(text: 'مؤرشف', icon: Icons.archive_outlined, neutral: true),
                  ],
                ],
              ),
              const SizedBox(height: 8),
              Text(
                account.balance == null ? 'الرصيد غير معروف' : '${formatMoney(account.balance!)} دينار',
                style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 6),
              Wrap(
                spacing: 8,
                runSpacing: 4,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  _QualityChip(quality: account.balanceQuality),
                  if (account.balanceAsOf != null)
                    Text('آخر رصيد مسجّل: ${relativeArabic(account.balanceAsOf!)}',
                        style: const TextStyle(fontSize: 12, color: AppColors.secondaryText)),
                ],
              ),
              if (account.transactionsSinceSnapshot > 0) ...[
                const SizedBox(height: 6),
                Text('يشمل ${account.transactionsSinceSnapshot} معاملة بعد آخر رصيد مسجّل',
                    style: const TextStyle(fontSize: 12, color: AppColors.secondaryText)),
              ],
              if (account.ignoredBeforeSnapshot > 0) ...[
                const SizedBox(height: 8),
                _Notice(
                  '${account.ignoredBeforeSnapshot} معاملة بتاريخ أقدم من آخر رصيد مسجّل ما انحسبت، '
                  'لأن الرصيد اللي أدخلته بيشملها.',
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _QualityChip extends StatelessWidget {
  final String quality;

  const _QualityChip({required this.quality});

  @override
  Widget build(BuildContext context) {
    switch (quality) {
      case kQualityManualConfirmed:
        return _Pill(text: balanceQualityLabel(quality), icon: Icons.check_circle_outline, neutral: true);
      case kQualityDerived:
        return _Pill(text: balanceQualityLabel(quality), icon: Icons.calculate_outlined, neutral: true);
      case kQualityStale:
        return _Pill(text: balanceQualityLabel(quality), icon: Icons.schedule, neutral: false);
      case kQualityUnknown:
      default:
        return _Pill(text: balanceQualityLabel(kQualityUnknown), icon: Icons.help_outline, neutral: false);
    }
  }
}

/// شارة بنص وأيقونة: الحالة بتنفهم من النص مش من اللون وحده.
class _Pill extends StatelessWidget {
  final String text;
  final IconData icon;
  final bool neutral;

  const _Pill({required this.text, required this.icon, required this.neutral});

  @override
  Widget build(BuildContext context) {
    final background = neutral ? TransactionTile.neutralBadgeBackground : TransactionTile.uncategorizedBadgeBackground;
    final foreground = neutral ? TransactionTile.neutralBadgeForeground : TransactionTile.uncategorizedBadgeForeground;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(color: background, borderRadius: BorderRadius.circular(10)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: foreground),
          const SizedBox(width: 4),
          Flexible(child: Text(text, style: TextStyle(fontSize: 12, color: foreground))),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  final VoidCallback onAdd;

  const _EmptyState({required this.onAdd});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 32, horizontal: 8),
      child: Column(
        children: [
          const Icon(Icons.account_balance_wallet_outlined, size: 48, color: AppColors.secondaryText),
          const SizedBox(height: 12),
          const Text('ما عندك حسابات مالية لسا', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          const Text(
            'إضافة رصيدك الحالي اختيارية بالكامل، والتطبيق بيشتغل عادي بدونها. '
            'هاي أرقام بتدخلها إنت بنفسك، مش ربط مع بنكك.',
            textAlign: TextAlign.center,
            style: TextStyle(color: AppColors.secondaryText),
          ),
          const SizedBox(height: 16),
          OutlinedButton.icon(onPressed: onAdd, icon: const Icon(Icons.add), label: const Text('أضف حساب')),
        ],
      ),
    );
  }
}

class _ErrorBox extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const _ErrorBox({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 16),
      child: Column(
        children: [
          Text(message, textAlign: TextAlign.center),
          const SizedBox(height: 12),
          OutlinedButton(onPressed: onRetry, child: const Text('إعادة المحاولة')),
        ],
      ),
    );
  }
}
