import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api_client.dart';
import '../core/financial_account_providers.dart';
import '../models/financial_account.dart';
import '../theme/app_theme.dart';

/// منتقي حساب اختياري للتسجيل السريع. بيظهر فقط إذا عند المستخدم حساب نشط واحد على الأقل؛
/// غير هيك ما بيظهر شي، فنفس الشاشة القديمة بالضبط لمن ما بيستخدم الحسابات. المؤرشفة ما بتظهر.
class QuickLogAccountPicker extends ConsumerWidget {
  final String? selectedId;
  final ValueChanged<String?> onChanged;

  const QuickLogAccountPicker({super.key, required this.selectedId, required this.onChanged});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final accounts = ref.watch(activeAccountsProvider).valueOrNull ?? const <FinancialAccount>[];
    if (accounts.isEmpty) return const SizedBox.shrink();

    // الحساب المختار انأرشف/انحذف بالأثناء: بنرجع لـ "بدون حساب" بدل ما نرسل حساب غير صالح
    final selectionIsValid = selectedId == null || accounts.any((account) => account.id == selectedId);
    if (!selectionIsValid) {
      WidgetsBinding.instance.addPostFrameCallback((_) => onChanged(null));
    }
    final effective = selectionIsValid ? selectedId : null;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('الحساب (اختياري)', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 4,
          children: [
            ChoiceChip(
              label: const Text('بدون حساب'),
              selected: effective == null,
              onSelected: (_) => onChanged(null),
            ),
            for (final account in accounts)
              ChoiceChip(
                label: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 180),
                  child: Text(account.name, maxLines: 1, overflow: TextOverflow.ellipsis),
                ),
                selected: effective == account.id,
                onSelected: (_) => onChanged(account.id),
              ),
          ],
        ),
      ],
    );
  }
}

/// نتيجة اختيار حساب بورقة النقل: accountId = null تعني "فك الربط". (الإغلاق بدون اختيار بيرجّع null للدالة كلها.)
class AccountChoice {
  final String? accountId;

  const AccountChoice(this.accountId);
}

/// ورقة اختيار الحساب لنقل معاملة أو ربطها أو فك ربطها. الحسابات المؤرشفة مش بالقائمة (السيرفر بيرفضها أصلاً).
Future<AccountChoice?> showAccountChoiceSheet(BuildContext context, {String? currentAccountId}) {
  return showModalBottomSheet<AccountChoice>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => _AccountChoiceSheet(currentAccountId: currentAccountId),
  );
}

class _AccountChoiceSheet extends ConsumerWidget {
  final String? currentAccountId;

  const _AccountChoiceSheet({this.currentAccountId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final accountsAsync = ref.watch(activeAccountsProvider);
    final directory = ref.watch(accountDirectoryProvider).valueOrNull;
    final currentIsArchived =
        currentAccountId != null && directory != null && directory[currentAccountId]?.isActive == false;

    return SafeArea(
      child: ConstrainedBox(
        constraints: BoxConstraints(maxHeight: MediaQuery.of(context).size.height * 0.7),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: 20),
                child: Text('اختار الحساب', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              ),
              if (currentIsArchived)
                const Padding(
                  padding: EdgeInsets.fromLTRB(20, 4, 20, 0),
                  child: Text('الحساب الحالي مؤرشف: ما بتقدر تنقل لحساب مؤرشف، بس بتقدر تفك الربط أو تنقل لحساب نشط.',
                      style: TextStyle(fontSize: 12, color: AppColors.secondaryText)),
                ),
              const SizedBox(height: 8),
              ListTile(
                leading: const Icon(Icons.link_off),
                title: const Text('بدون حساب (فك الربط)'),
                trailing: currentAccountId == null ? const Icon(Icons.check) : null,
                onTap: () => Navigator.of(context).pop(const AccountChoice(null)),
              ),
              accountsAsync.when(
                loading: () => const Padding(padding: EdgeInsets.all(24), child: Center(child: CircularProgressIndicator())),
                error: (error, _) => Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    children: [
                      Text(error is ApiException ? error.message : 'صار خطأ غير متوقع، جرب كمان شوي',
                          textAlign: TextAlign.center),
                      const SizedBox(height: 12),
                      OutlinedButton(
                        onPressed: () => ref.invalidate(activeAccountsProvider),
                        child: const Text('إعادة المحاولة'),
                      ),
                    ],
                  ),
                ),
                data: (accounts) => Column(
                  children: [
                    for (final account in accounts)
                      ListTile(
                        leading: const Icon(Icons.account_balance_wallet_outlined),
                        title: Text(account.name, maxLines: 1, overflow: TextOverflow.ellipsis),
                        subtitle: Text(accountKindLabel(account.kind)),
                        trailing: currentAccountId == account.id ? const Icon(Icons.check) : null,
                        onTap: () => Navigator.of(context).pop(AccountChoice(account.id)),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
