class ReceiptScanResult {
  final double? amount;
  final String? categoryId;
  final String? categoryName;
  final String? note;

  final bool readable;

  ReceiptScanResult({
    required this.amount,
    required this.categoryId,
    required this.categoryName,
    required this.note,
    required this.readable,
  });

  factory ReceiptScanResult.fromJson(Map<String, dynamic> json) {
    return ReceiptScanResult(
      amount: (json['amount'] as num?)?.toDouble(),
      categoryId: json['category_id'] as String?,
      categoryName: json['category_name'] as String?,
      note: json['note'] as String?,
      readable: json['readable'] as bool? ?? false,
    );
  }
}
