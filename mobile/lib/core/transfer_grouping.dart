import '../models/transaction.dart';

/// دمج طرفي التحويل الداخلي بسطر واحد بقائمة المعاملات (عرض فقط، بدون أي حساب أرصدة).
/// طرف الخروج نوعه expense وطرف الدخول income، وبيشتركوا بـ transferGroupId.
class TransferEntry {
  final String groupId;
  final Transaction? outLeg;
  final Transaction? inLeg;

  TransferEntry({required this.groupId, this.outLeg, this.inLeg});

  /// أي طرف موجود بالقائمة (المبلغ والوقت والملاحظة نفسها على الطرفين).
  Transaction get anyLeg => (outLeg ?? inLeg)!;

  double get amount => anyLeg.amount;
  DateTime get occurredAt => anyLeg.occurredAt;
  String? get note => anyLeg.note;
  String? get fromAccountId => outLeg?.accountId;
  String? get toAccountId => inLeg?.accountId;

  /// true لما أحد الطرفين مش ظاهر بالقائمة (مثلاً انقص بحد عدد المعاملات المعروضة).
  bool get isPartial => outLeg == null || inLeg == null;
}

/// عنصر بالقائمة: معاملة عادية، أو تحويل مدموج.
class TransactionListEntry {
  final Transaction? transaction;
  final TransferEntry? transfer;

  const TransactionListEntry.single(Transaction this.transaction) : transfer = null;
  const TransactionListEntry.transfer(TransferEntry this.transfer) : transaction = null;
}

class _TransferBuilder {
  final String groupId;
  Transaction? outLeg;
  Transaction? inLeg;

  _TransferBuilder(this.groupId);

  bool accepts(Transaction leg) => leg.type == 'expense' ? outLeg == null : inLeg == null;

  void add(Transaction leg) {
    if (leg.type == 'expense') {
      outLeg = leg;
    } else {
      inLeg = leg;
    }
  }

  TransferEntry build() => TransferEntry(groupId: groupId, outLeg: outLeg, inLeg: inLeg);
}

/// بيحافظ على ترتيب القائمة: التحويل بيطلع بمكان أول طرف منه. طرف وحيد بيضل تحويلاً جزئيًا (بدون تخمين بالطرف الثاني).
List<TransactionListEntry> groupTransfers(List<Transaction> transactions) {
  final entries = <Object>[]; // Transaction أو _TransferBuilder
  final open = <String, _TransferBuilder>{};

  for (final transaction in transactions) {
    final groupId = transaction.transferGroupId;
    if (!transaction.isTransfer || groupId == null) {
      entries.add(transaction);
      continue;
    }
    final existing = open[groupId];
    if (existing != null && existing.accepts(transaction)) {
      existing.add(transaction);
      continue;
    }
    // أول طرف بالمجموعة، أو طرف مكرر النوع (بيانات غير متوقعة): بنعرضه لحاله بدل ما نخسره
    final builder = _TransferBuilder(groupId)..add(transaction);
    open[groupId] = builder;
    entries.add(builder);
  }

  return [
    for (final entry in entries)
      if (entry is _TransferBuilder)
        TransactionListEntry.transfer(entry.build())
      else
        TransactionListEntry.single(entry as Transaction),
  ];
}
