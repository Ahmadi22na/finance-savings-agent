

class RawSms {
  final String body;
  final DateTime receivedAt;

  RawSms({required this.body, required this.receivedAt});

  Map<String, dynamic> toJson() => {
        'body': body,
        'received_at': receivedAt.toUtc().toIso8601String(),
      };
}



class SmsImportCandidate {
  final String body;
  final DateTime receivedAt;
  final double amount;
  final String type; // 'income' | 'expense'
  final String note;
  final bool alreadyImported;
  final bool possibleDuplicate; // تنبيه من السيرفر: يشبه رسالة لصقها المستخدم يدويًا (لا يمنع الاستيراد)

  SmsImportCandidate({
    required this.body,
    required this.receivedAt,
    required this.amount,
    required this.type,
    required this.note,
    required this.alreadyImported,
    this.possibleDuplicate = false,
  });

  factory SmsImportCandidate.fromJson(Map<String, dynamic> json) {
    return SmsImportCandidate(
      body: json['body'] as String,
      receivedAt: DateTime.parse(json['received_at'] as String),
      amount: (json['amount'] as num).toDouble(),
      type: json['type'] as String,
      note: json['note'] as String,
      alreadyImported: json['already_imported'] as bool? ?? false,
      possibleDuplicate: json['possible_duplicate'] as bool? ?? false,
    );
  }



  RawSms toRawSms() => RawSms(body: body, receivedAt: receivedAt);
}
