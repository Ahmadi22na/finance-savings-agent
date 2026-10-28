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
  final String? categoryOrigin; // user | auto | null
  final double? categoryConfidence; // 0..1 عندما يكون التصنيف تلقائيًا
  final String? accountId; // الحساب المالي المرتبطة به (اختياري)
  final bool isTransfer; // طرف من تحويل داخلي بين حسابين (مش دخل ولا مصروف حقيقي)
  final String? transferGroupId; // طرفا التحويل يشتركان فيه

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
    this.categoryOrigin,
    this.categoryConfidence,
    this.accountId,
    this.isTransfer = false,
    this.transferGroupId,
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
      categoryOrigin: json['category_origin'] as String?,
      categoryConfidence: (json['category_confidence'] as num?)?.toDouble(),
      accountId: json['account_id'] as String?,
      isTransfer: json['is_transfer'] as bool? ?? false,
      transferGroupId: json['transfer_group_id'] as String?,
    );
  }
}
