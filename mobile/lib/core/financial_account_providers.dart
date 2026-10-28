import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/financial_account.dart';
import 'providers.dart';

/// الحسابات المؤرشفة مخفية افتراضيًا.
final showArchivedAccountsProvider = StateProvider<bool>((ref) => false);

final financialAccountsProvider = FutureProvider.autoDispose<List<FinancialAccount>>((ref) async {
  final includeArchived = ref.watch(showArchivedAccountsProvider);
  return ref.watch(financialAccountServiceProvider).listAccounts(includeArchived: includeArchived);
});

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
}
