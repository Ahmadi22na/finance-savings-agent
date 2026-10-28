import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/financial_account.dart';
import 'providers.dart';

/// الحسابات المؤرشفة مخفية افتراضيًا.
final showArchivedAccountsProvider = StateProvider<bool>((ref) => false);

final financialAccountsProvider = FutureProvider.autoDispose<List<FinancialAccount>>((ref) async {
  final includeArchived = ref.watch(showArchivedAccountsProvider);
  return ref.watch(financialAccountServiceProvider).listAccounts(includeArchived: includeArchived);
});

/// الحسابات النشطة فقط (للمنتقيات: التسجيل السريع، النقل، التحويل) — مستقلة عن مفتاح "عرض المؤرشفة".
final activeAccountsProvider = FutureProvider.autoDispose<List<FinancialAccount>>((ref) async {
  return ref.watch(financialAccountServiceProvider).listAccounts(includeArchived: false);
});

/// دليل كل الحسابات (بما فيها المؤرشفة) حسب id: لعرض اسم الحساب بشارة المعاملة والتحويل.
final accountDirectoryProvider = FutureProvider.autoDispose<Map<String, FinancialAccount>>((ref) async {
  final accounts = await ref.watch(financialAccountServiceProvider).listAccounts(includeArchived: true);
  return {for (final account in accounts) account.id: account};
});

/// آخر حساب انختار بالتسجيل السريع (بالذاكرة لجلسة التطبيق فقط، بدون تخزين محلي).
final lastQuickLogAccountIdProvider = StateProvider<String?>((ref) => null);

/// المجموع بيجي من ملخص السيرفر (incomplete وتعريفه عند السيرفر)، مش من جمع الواجهة.
final accountsSummaryProvider = FutureProvider.autoDispose<AccountsSummary>((ref) async {
  return ref.watch(financialAccountServiceProvider).getSummary();
});

/// سجل اللقطات (للمراجعة فقط).
final accountSnapshotsProvider =
    FutureProvider.autoDispose.family<List<BalanceSnapshot>, String>((ref, accountId) async {
  return ref.watch(financialAccountServiceProvider).listSnapshots(accountId);
});

void refreshFinancialAccounts(WidgetRef ref) {
  ref.invalidate(financialAccountsProvider);
  ref.invalidate(accountsSummaryProvider);
  ref.invalidate(activeAccountsProvider);
  ref.invalidate(accountDirectoryProvider);
}
