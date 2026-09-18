import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/transaction.dart';
import '../theme/icon_mapper.dart';

class TransactionTile extends StatelessWidget {
  final Transaction transaction;

  const TransactionTile({super.key, required this.transaction});

  @override
  Widget build(BuildContext context) {
    final isIncome = transaction.type == 'income';
    final amountColor = isIncome ? Colors.green.shade700 : Colors.red.shade700;
    final amountPrefix = isIncome ? '+' : '-';
    final categoryName = transaction.category?.name ?? (transaction.note ?? 'بدون تصنيف');
    final iconKey = transaction.category?.icon ?? 'tag';

    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: CircleAvatar(
        backgroundColor: Colors.grey.shade100,
        child: Icon(iconForKey(iconKey), color: Colors.black54, size: 20),
      ),
      title: Text(categoryName, style: const TextStyle(fontWeight: FontWeight.w600)),
      subtitle: Text(
        DateFormat('d/M - HH:mm').format(transaction.occurredAt),
        style: const TextStyle(fontSize: 12),
      ),
      trailing: Text(
        '$amountPrefix${transaction.amount.toStringAsFixed(1)}',
        style: TextStyle(color: amountColor, fontWeight: FontWeight.bold, fontSize: 15),
      ),
    );
  }
}
