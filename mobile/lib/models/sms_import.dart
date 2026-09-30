/// رسالة خام مقروءة من صندوق الوارد — هاد كل شي بيطلع من الجهاز للسيرفر
/// (نص الرسالة ووقت استلامها)، وبعد فلترة محلية بتبقّي بس الرسائل المالية.
class RawSms {
  final String body;
  final DateTime receivedAt;

  RawSms({required this.body, required this.receivedAt});

  Map<String, dynamic> toJson() => {
        'body': body,
        'received_at': receivedAt.toUtc().toIso8601String(),
      };
}

/// معاملة مقترحة من رسالة — السيرفر هو يلي حلّلها (المبلغ والنوع)،
/// الموبايل بس بيعرضها ويخلي المستخدم يختار.
class SmsImportCandidate {
  final String body;
  final DateTime receivedAt;
  final double amount;
  final String type; // 'income' | 'expense'
  final String note;
  final bool alreadyImported;

  SmsImportCandidate({
    required this.body,
    required this.receivedAt,
    required this.amount,
    required this.type,
    required this.note,
    required this.alreadyImported,
  });

  factory SmsImportCandidate.fromJson(Map<String, dynamic> json) {
    return SmsImportCandidate(
      body: json['body'] as String,
      receivedAt: DateTime.parse(json['received_at'] as String),
      amount: (json['amount'] as num).toDouble(),
      type: json['type'] as String,
      note: json['note'] as String,
      alreadyImported: json['already_imported'] as bool? ?? false,
    );
  }

  /// للتأكيد بنرجّع نفس النص ووقته بالضبط — السيرفر بيعيد التحليل وبيحسب
  /// نفس البصمة، فما في داعي نبعت المبلغ أو النوع أبدًا.
  RawSms toRawSms() => RawSms(body: body, receivedAt: receivedAt);
}
