import 'category.dart';


class Transaction {
  final String id;
  final double amount;
  final String type; // income | expense
  final String source; // manual | ocr | sms | open_banking
  final String? note;
  final DateTime occurredAt;
  final Category? category;
  final bool aiSuggested;
  final double? suggestionConfidence;
  final double unallocatedAmount;

  Transaction({
    required this.id,
    required this.amount,
    required this.type,
    required this.source,
    required this.note,
    required this.occurredAt,
    required this.category,
    required this.aiSuggested,
    required this.suggestionConfidence,
    required this.unallocatedAmount,
  });

  factory Transaction.fromJson(Map<String, dynamic> json) {
    return Transaction(
      id: json['id'] as String,
      amount: (json['amount'] as num).toDouble(),
      type: json['type'] as String,
      source: json['source'] as String,
      note: json['note'] as String?,
      occurredAt: DateTime.parse(json['occurred_at'] as String),
      category: json['category'] != null
          ? Category.fromJson(json['category'] as Map<String, dynamic>)
          : null,
      aiSuggested: json['ai_suggested'] as bool? ?? false,
      suggestionConfidence: (json['suggestion_confidence'] as num?)?.toDouble(),
      unallocatedAmount: (json['unallocated_amount'] as num?)?.toDouble() ?? 0,
    );
  }
}
