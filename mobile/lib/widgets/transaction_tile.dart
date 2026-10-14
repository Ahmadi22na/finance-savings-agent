import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/transaction.dart';
import '../theme/icon_mapper.dart';

/// سطر معاملة مع شارات واضحة: مصدرها (يدوي / فاتورة / رسالة بنكية)، وهل التصنيف تلقائي (مع درجة الثقة)
/// أو غير موجود. الضغط عليه بيفتح تعديل التصنيف (لو onTap مُمرَّر).
class TransactionTile extends StatelessWidget {
  final Transaction transaction;
  final VoidCallback? onTap;

  const TransactionTile({super.key, required this.transaction, this.onTap});

  static String sourceLabel(String source) {
    switch (source) {
      case 'ocr':
        return 'فاتورة';
      case 'sms':
        return 'رسالة بنكية';
      case 'open_banking':
        return 'بنك';
      default:
        return 'يدوي';
    }
  }

  static IconData sourceIcon(String source) {
    switch (source) {
      case 'ocr':
        return Icons.receipt_long_outlined;
      case 'sms':
        return Icons.sms_outlined;
      case 'open_banking':
        return Icons.account_balance_outlined;
      default:
        return Icons.edit_outlined;
    }
  }

  @override
  Widget build(BuildContext context) {
    final isIncome = transaction.type == 'income';
    final amountColor = isIncome ? Colors.green.shade700 : Colors.red.shade700;
    final amountPrefix = isIncome ? '+' : '-';
    final categoryName = transaction.category?.name ?? (transaction.note ?? 'بدون تصنيف');
    final iconKey = transaction.category?.icon ?? 'tag';
    final isAuto = transaction.categoryOrigin == 'auto';
    final confidence = transaction.categoryConfidence;

    return ListTile(
      contentPadding: EdgeInsets.zero,
      onTap: onTap,
      leading: CircleAvatar(
        backgroundColor: Colors.grey.shade100,
        child: Icon(iconForKey(iconKey), color: Colors.black54, size: 20),
      ),
      title: Text(categoryName, style: const TextStyle(fontWeight: FontWeight.w600)),
      subtitle: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            DateFormat('d/M - HH:mm').format(transaction.occurredAt),
            style: const TextStyle(fontSize: 12),
          ),
          const SizedBox(height: 4),
          Wrap(
            spacing: 6,
            runSpacing: 4,
            children: [
              _MiniBadge(
                icon: sourceIcon(transaction.source),
                label: sourceLabel(transaction.source),
                background: Colors.grey.shade200,
                foreground: Colors.black54,
              ),
              if (isAuto)
                _MiniBadge(
                  icon: Icons.auto_awesome,
                  label: confidence != null
                      ? 'تصنيف تلقائي ${(confidence * 100).round()}%'
                      : 'تصنيف تلقائي',
                  background: Colors.amber.shade100,
                  foreground: Colors.amber.shade900,
                ),
              if (transaction.category == null)
                _MiniBadge(
                  icon: Icons.label_off_outlined,
                  label: 'بدون تصنيف',
                  background: Colors.orange.shade50,
                  foreground: Colors.orange.shade800,
                ),
            ],
          ),
        ],
      ),
      trailing: Text(
        '$amountPrefix${transaction.amount.toStringAsFixed(1)}',
        style: TextStyle(color: amountColor, fontWeight: FontWeight.bold, fontSize: 15),
      ),
    );
  }
}

class _MiniBadge extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color background;
  final Color foreground;

  const _MiniBadge({
    required this.icon,
    required this.label,
    required this.background,
    required this.foreground,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: foreground),
          const SizedBox(width: 4),
          Text(label, style: TextStyle(fontSize: 11, color: foreground)),
        ],
      ),
    );
  }
}
