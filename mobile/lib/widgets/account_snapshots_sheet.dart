import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../core/account_format.dart';
import '../core/api_client.dart';
import '../core/financial_account_providers.dart';
import '../models/financial_account.dart';
import '../theme/app_theme.dart';

/// سجل لقطات رصيد الحساب: للمراجعة فقط. عرض لقطة قديمة ما بيغيّر الرصيد الحالي وما فيه أي إجراء عليها.
Future<void> showAccountSnapshotsSheet(BuildContext context, FinancialAccount account) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => _AccountSnapshotsSheet(account: account),
  );
}

class _AccountSnapshotsSheet extends ConsumerWidget {
  final FinancialAccount account;

  const _AccountSnapshotsSheet({required this.account});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final snapshotsAsync = ref.watch(accountSnapshotsProvider(account.id));
    final dateFormat = DateFormat('d/M/yyyy - HH:mm');

    return SafeArea(
      child: ConstrainedBox(
        constraints: BoxConstraints(maxHeight: MediaQuery.of(context).size.height * 0.7),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Text('سجل أرصدة ${account.name}',
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            ),
            const Padding(
              padding: EdgeInsets.fromLTRB(20, 4, 20, 8),
              child: Text(
                'للمراجعة فقط — عرض رصيد قديم ما بيغيّر الرصيد الحالي. لتصحيح رصيدك سجّل رصيدًا جديدًا.',
                style: TextStyle(fontSize: 12, color: AppColors.secondaryText),
              ),
            ),
            Flexible(
              child: snapshotsAsync.when(
                loading: () => const Padding(
                  padding: EdgeInsets.all(32),
                  child: Center(child: CircularProgressIndicator()),
                ),
                error: (error, _) => Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(error is ApiException ? error.message : 'صار خطأ غير متوقع، جرب كمان شوي',
                          textAlign: TextAlign.center),
                      const SizedBox(height: 12),
                      OutlinedButton(
                        onPressed: () => ref.invalidate(accountSnapshotsProvider(account.id)),
                        child: const Text('إعادة المحاولة'),
                      ),
                    ],
                  ),
                ),
                data: (snapshots) {
                  if (snapshots.isEmpty) {
                    return const Padding(
                      padding: EdgeInsets.all(24),
                      child: Text('ما في أرصدة مسجّلة لهالحساب لسا.'),
                    );
                  }
                  return ListView.separated(
                    shrinkWrap: true,
                    itemCount: snapshots.length,
                    separatorBuilder: (_, __) => const Divider(height: 1),
                    itemBuilder: (context, index) {
                      final snapshot = snapshots[index];
                      return ListTile(
                        title: Text('${formatMoney(snapshot.amount)} دينار'),
                        subtitle: Text(
                          'الوقت: ${dateFormat.format(snapshot.asOf.toLocal())}\n'
                          'المصدر: ${snapshotSourceLabel(snapshot.source)} • سُجّل ${relativeArabic(snapshot.createdAt)}',
                        ),
                        isThreeLine: true,
                      );
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
