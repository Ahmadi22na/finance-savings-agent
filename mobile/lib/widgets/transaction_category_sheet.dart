import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api_client.dart';
import '../core/dashboard_providers.dart';
import '../core/providers.dart';
import '../models/category.dart';
import '../models/transaction.dart';
import '../theme/icon_mapper.dart';
import '../core/financial_account_providers.dart';
import 'account_picker.dart';
import 'transaction_edit_sheet.dart';
import 'transaction_tile.dart';
import '../theme/app_theme.dart';

/// ورقة سفلية لتعديل معاملة: التصنيف مباشرة، ومعها زرّي "تعديل المبلغ والملاحظة" و"حذف المعاملة".
/// (التصنيف: بتعرض التصنيفات المناسبة لنوعها، وبعد الاختيار بيتحفظ التعديل
/// بالسيرفر وبتتحدّث القائمة. (بعد التعديل بتختفي شارة "تصنيف تلقائي" لأنه صار قرار المستخدم.)
Future<void> showTransactionCategorySheet(BuildContext context, Transaction transaction) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => _TransactionCategorySheet(transaction: transaction),
  );
}

class _TransactionCategorySheet extends ConsumerStatefulWidget {
  final Transaction transaction;

  const _TransactionCategorySheet({required this.transaction});

  @override
  ConsumerState<_TransactionCategorySheet> createState() => _TransactionCategorySheetState();
}

class _TransactionCategorySheetState extends ConsumerState<_TransactionCategorySheet> {
  bool _isSaving = false;

  static String _formatAmount(double value) {
    if (value == value.roundToDouble()) return value.toStringAsFixed(0);
    return value.toStringAsFixed(3).replaceFirst(RegExp(r'0+$'), '');
  }

  Future<void> _openEdit() async {
    final saved = await showTransactionEditSheet(context, widget.transaction);
    if (saved == true && mounted) {
      refreshFinancialAccounts(ref); // المبلغ والتاريخ بيغيّروا رصيد الحساب المرتبطة فيه
      Navigator.of(context).pop();
    }
  }

  Future<void> _moveAccount() async {
    final transaction = widget.transaction;
    final choice = await showAccountChoiceSheet(context, currentAccountId: transaction.accountId);
    if (choice == null || !mounted || choice.accountId == transaction.accountId) return;

    final messenger = ScaffoldMessenger.of(context);
    setState(() => _isSaving = true);
    try {
      await ref.read(transactionServiceProvider).moveToAccount(transaction.id, choice.accountId);
      ref.invalidate(recentTransactionsProvider);
      refreshFinancialAccounts(ref);
      if (!mounted) return;
      Navigator.of(context).pop();
      messenger.showSnackBar(SnackBar(
        content: Text(choice.accountId == null ? 'تم فك ربط المعاملة بالحساب' : 'تم ربط المعاملة بالحساب ✅'),
      ));
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _isSaving = false);
      messenger.showSnackBar(SnackBar(content: Text(e.message)));
    } catch (_) {
      if (!mounted) return;
      setState(() => _isSaving = false);
      messenger.showSnackBar(const SnackBar(content: Text('ما قدرنا ننفّذ الطلب، جرب كمان شوي')));
    }
  }

  Future<void> _confirmDelete() async {
    final transaction = widget.transaction;
    final allocated = transaction.type == 'income' ? transaction.amount - transaction.unallocatedAmount : 0.0;
    final hasAllocation = allocated > 0.0005;

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('حذف المعاملة؟'),
        content: Text(
          hasAllocation
              ? 'جزء من هالدخل (${_formatAmount(allocated)} دينار) موزَّع على أهدافك. إذا حذفتها، هالمبلغ بينقص من الأهداف المعنية. ما بتقدر تتراجع.'
              : 'رح تنحذف هالمعاملة نهائيًا وما بتقدر تتراجع.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('إلغاء'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: TransactionTile.expenseColor),
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('احذف'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    final messenger = ScaffoldMessenger.of(context);
    setState(() => _isSaving = true);
    try {
      await ref.read(transactionServiceProvider).deleteTransaction(transaction.id);
      ref.invalidate(recentTransactionsProvider);
      ref.invalidate(goalsListProvider); // مبالغ الأهداف ممكن تتغيّر بعد عكس التوزيع
      refreshFinancialAccounts(ref); // وأرصدة الحسابات لو كانت مرتبطة بحساب
      if (!mounted) return;
      Navigator.of(context).pop();
      messenger.showSnackBar(const SnackBar(content: Text('تم حذف المعاملة')));
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _isSaving = false);
      messenger.showSnackBar(SnackBar(content: Text(e.message)));
    } catch (_) {
      if (!mounted) return;
      setState(() => _isSaving = false);
      messenger.showSnackBar(const SnackBar(content: Text('ما قدرنا نحذف المعاملة، جرب كمان شوي')));
    }
  }

  Future<void> _save(String? categoryId) async {
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _isSaving = true);
    try {
      await ref.read(transactionServiceProvider).updateCategory(widget.transaction.id, categoryId);
      ref.invalidate(recentTransactionsProvider);
      if (!mounted) return;
      Navigator.of(context).pop();
      messenger.showSnackBar(
        const SnackBar(content: Text('تم تعديل التصنيف ✅')),
      );
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _isSaving = false);
      messenger.showSnackBar(SnackBar(content: Text(e.message)));
    } catch (_) {
      if (!mounted) return;
      setState(() => _isSaving = false);
      messenger.showSnackBar(
        const SnackBar(content: Text('ما قدرنا نحفظ التعديل، جرب كمان شوي')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    // زر الربط/النقل بيظهر بس لمن عنده حساب نشط، أو لمعاملة مرتبطة أصلاً بحساب (عشان يقدر يفك الربط)
    final hasActiveAccounts = ref.watch(activeAccountsProvider).maybeWhen(data: (list) => list.isNotEmpty, orElse: () => false);
    final canMoveAccount = hasActiveAccounts || widget.transaction.accountId != null;
    final transaction = widget.transaction;
    final categoriesAsync = ref.watch(categoriesListProvider);
    final isAuto = transaction.categoryOrigin == 'auto';
    final confidence = transaction.categoryConfidence;
    final typeLabel = transaction.type == 'income' ? 'دخل' : 'مصروف';

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('تعديل التصنيف', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 6),
            Text(
              '$typeLabel ${transaction.amount.toStringAsFixed(2)} دينار · '
              '${TransactionTile.sourceLabel(transaction.source)}',
              style: const TextStyle(color: AppColors.secondaryText, fontSize: 13),
            ),
            if (isAuto) ...[
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: Colors.amber.shade50,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.auto_awesome, size: 16, color: TransactionTile.autoBadgeForeground),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        confidence != null
                            ? 'صنّفها رشيد تلقائيًا بثقة ${(confidence * 100).round()}%. إذا مش صح، اختار التصنيف الصحيح.'
                            : 'صنّفها رشيد تلقائيًا. إذا مش صح، اختار التصنيف الصحيح.',
                        style: const TextStyle(fontSize: 12, height: 1.4),
                      ),
                    ),
                  ],
                ),
              ),
            ],
            const SizedBox(height: 16),
            categoriesAsync.when(
              loading: () => const Center(
                child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator()),
              ),
              error: (_, __) => const Text('ما قدرنا نحمّل التصنيفات، جرب كمان شوي'),
              data: (all) => _buildChoices(all),
            ),
            const SizedBox(height: 12),
            const Divider(),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: _isSaving ? null : _openEdit,
                icon: const Icon(Icons.edit_outlined, size: 18),
                label: const Text('تعديل المبلغ والملاحظة'),
              ),
            ),
            if (canMoveAccount) ...[
              const SizedBox(height: 8),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: _isSaving ? null : _moveAccount,
                  icon: const Icon(Icons.account_balance_wallet_outlined, size: 18),
                  label: Text(widget.transaction.accountId == null ? 'ربط بحساب مالي' : 'نقل لحساب آخر / فك الربط'),
                ),
              ),
            ],
            const SizedBox(height: 8),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: _isSaving ? null : _confirmDelete,
                style: OutlinedButton.styleFrom(foregroundColor: TransactionTile.expenseColor),
                icon: const Icon(Icons.delete_outline, size: 18),
                label: const Text('حذف المعاملة'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildChoices(List<Category> all) {
    final transaction = widget.transaction;
    final suitable = all
        .where((c) => c.categoryType == 'both' || c.categoryType == transaction.type)
        .toList();
    final currentId = transaction.category?.id;

    return Flexible(
      child: SingleChildScrollView(
        child: Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final category in suitable)
              ChoiceChip(
                avatar: Icon(iconForKey(category.icon), size: 16),
                label: Text(category.name),
                selected: category.id == currentId,
                onSelected: _isSaving ? null : (_) => _save(category.id),
              ),
            if (currentId != null)
              ActionChip(
                avatar: const Icon(Icons.label_off_outlined, size: 16),
                label: const Text('بدون تصنيف'),
                onPressed: _isSaving ? null : () => _save(null),
              ),
          ],
        ),
      ),
    );
  }
}
