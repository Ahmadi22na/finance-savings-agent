class SmsParseResult {
  final double? amount;
  final String? type; // 'income' | 'expense' | null
  final String? note;

  final bool parsed;

  SmsParseResult({
    required this.amount,
    required this.type,
    required this.note,
    required this.parsed,
  });

  factory SmsParseResult.fromJson(Map<String, dynamic> json) {
    return SmsParseResult(
      amount: (json['amount'] as num?)?.toDouble(),
      type: json['type'] as String?,
      note: json['note'] as String?,
      parsed: json['parsed'] as bool? ?? false,
    );
  }
}
