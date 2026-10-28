import 'package:flutter_test/flutter_test.dart';

import 'package:rasheed_app/core/transfer_grouping.dart';
import 'package:rasheed_app/models/transaction.dart';

Transaction tx(
  String id, {
  String type = 'expense',
  String? group,
  String? account,
  double amount = 10,
  String? note,
  String time = '2026-10-25T10:00:00Z',
}) {
  return Transaction.fromJson({
    'id': id,
    'amount': amount,
    'type': type,
    'source': 'manual',
    'note': note,
    'occurred_at': time,
    'category': null,
    'account_id': account,
    'is_transfer': group != null,
    'transfer_group_id': group,
  });
}

String describe(List<TransactionListEntry> entries) => entries
    .map((entry) => entry.transfer != null ? 'T:${entry.transfer!.groupId}' : 'S:${entry.transaction!.id}')
    .join(',');

void main() {
  group('groupTransfers', () {
    test('قائمة بدون تحويلات بتضل كما هي بنفس الترتيب', () {
      final entries = groupTransfers([tx('a'), tx('b', type: 'income'), tx('c')]);
      expect(describe(entries), 'S:a,S:b,S:c');
      expect(entries.every((e) => e.transfer == null), isTrue);
    });

    test('طرفا التحويل بيندمجوا بسطر واحد بمكان أول طرف', () {
      final entries = groupTransfers([
        tx('x'),
        tx('out', group: 'g1', account: 'A', note: 'تعبئة'),
        tx('mid'),
        tx('in', group: 'g1', account: 'B', type: 'income', note: 'تعبئة'),
      ]);
      expect(describe(entries), 'S:x,T:g1,S:mid');

      final transfer = entries[1].transfer!;
      expect(transfer.isPartial, isFalse);
      expect(transfer.fromAccountId, 'A');
      expect(transfer.toAccountId, 'B');
      expect(transfer.amount, 10);
      expect(transfer.note, 'تعبئة');
    });

    test('نفس النتيجة لو طرف الدخول جاء أول', () {
      final entries = groupTransfers([
        tx('in', group: 'g1', account: 'B', type: 'income'),
        tx('out', group: 'g1', account: 'A'),
      ]);
      expect(describe(entries), 'T:g1');
      expect(entries.single.transfer!.fromAccountId, 'A');
      expect(entries.single.transfer!.toAccountId, 'B');
    });

    test('طرف وحيد بالقائمة بيضل تحويل جزئي بدون تخمين بالطرف الثاني', () {
      final outOnly = groupTransfers([tx('out', group: 'g1', account: 'A')]).single.transfer!;
      expect(outOnly.isPartial, isTrue);
      expect(outOnly.outLeg, isNotNull);
      expect(outOnly.inLeg, isNull);
      expect(outOnly.fromAccountId, 'A');
      expect(outOnly.toAccountId, isNull);

      final inOnly = groupTransfers([tx('in', group: 'g1', account: 'B', type: 'income')]).single.transfer!;
      expect(inOnly.isPartial, isTrue);
      expect(inOnly.fromAccountId, isNull);
      expect(inOnly.toAccountId, 'B');
    });

    test('أكتر من تحويل متداخلين مع معاملات عادية', () {
      final entries = groupTransfers([
        tx('o1', group: 'g1', account: 'A'),
        tx('o2', group: 'g2', account: 'B'),
        tx('n1'),
        tx('i1', group: 'g1', account: 'B', type: 'income'),
        tx('i2', group: 'g2', account: 'A', type: 'income'),
        tx('n2', type: 'income'),
      ]);
      expect(describe(entries), 'T:g1,T:g2,S:n1,S:n2');
      expect(entries[0].transfer!.isPartial, isFalse);
      expect(entries[1].transfer!.isPartial, isFalse);
      expect(entries[1].transfer!.fromAccountId, 'B');
      expect(entries[1].transfer!.toAccountId, 'A');
    });

    test('طرفان من نفس النوع (بيانات غير متوقعة) ما بينخسروا', () {
      final entries = groupTransfers([
        tx('o1', group: 'g1', account: 'A'),
        tx('o2', group: 'g1', account: 'B'),
      ]);
      expect(entries.length, 2);
      expect(entries.every((e) => e.transfer != null), isTrue);
    });

    test('معاملة بمجموعة بدون علامة تحويل بتنعتبر عادية', () {
      final odd = Transaction.fromJson({
        'id': 'z', 'amount': 5, 'type': 'expense', 'source': 'manual', 'occurred_at': '2026-10-25T10:00:00Z',
        'category': null, 'is_transfer': false, 'transfer_group_id': 'g9',
      });
      expect(describe(groupTransfers([odd])), 'S:z');
    });
  });

  group('Transaction.fromJson (الحقول الجديدة)', () {
    test('الرد القديم بدون الحقول بيشتغل: بدون حساب وليس تحويل', () {
      final parsed = Transaction.fromJson({
        'id': 'a', 'amount': 3, 'type': 'expense', 'source': 'manual', 'occurred_at': '2026-10-25T10:00:00Z',
        'category': null,
      });
      expect(parsed.accountId, isNull);
      expect(parsed.isTransfer, isFalse);
      expect(parsed.transferGroupId, isNull);
    });

    test('بيقرا حساب المعاملة وعلامة التحويل ومجموعته', () {
      final parsed = tx('a', group: 'g1', account: 'A');
      expect(parsed.accountId, 'A');
      expect(parsed.isTransfer, isTrue);
      expect(parsed.transferGroupId, 'g1');
    });
  });
}
