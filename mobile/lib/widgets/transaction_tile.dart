import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/transaction.dart';
import '../theme/icon_mapper.dart';
import '../theme/app_theme.dart';

/// سطر معاملة مع شارات واضحة: مصدرها (يدوي / فاتورة / رسالة بنكية)، وهل التصنيف تلقائي (مع درجة الثقة)
/// أو غير موجود. الضغط عليه بيفتح تعديل التصنيف (لو onTap مُمرَّر).
class TransactionTile extends StatelessWidget {
  final Transaction transaction;
  final VoidCallback? onTap;

  /// اسم الحساب المالي المرتبطة به المعاملة (اختياري). بدون حسابات بيضل السطر نفسه بالضبط.
  final String? accountName;
  final bool accountArchived;

  const TransactionTile({
    super.key,
    required this.transaction,
    this.onTap,
    this.accountName,
    this.accountArchived = false,
  });

  static String _shorten(String name) => name.length <= 22 ? name : '${name.substring(0, 21)}…';

  // ألوان بتحقق تباين WCAG AA (≥ 4.5:1) على خلفياتها — مغطّاة باختبار test/accessibility_test.dart
  static const Color incomeColor = Color(0xFF2E7D32);
  static const Color expenseColor = Color(0xFFC62828);
  static const Color neutralBadgeBackground = Color(0xFFEEEEEE);
  static const Color neutralBadgeForeground = Color(0xFF212121);
  static const Color autoBadgeBackground = Color(0xFFFFECB3);
  static const Color autoBadgeForeground = Color(0xFF6D4C00);
  static const Color uncategorizedBadgeBackground = Color(0xFFFFF3E0);
  static const Color uncategorizedBadgeForeground = Color(0xFF8F3A00);

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
    final amountColor = isIncome ? incomeColor : expenseColor;
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
        child: Icon(iconForKey(iconKey), color: AppColors.secondaryText, size: 20),
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
                background: neutralBadgeBackground,
                foreground: neutralBadgeForeground,
              ),
              if (accountName != null)
                _MiniBadge(
                  icon: Icons.account_balance_wallet_outlined,
                  label: accountArchived ? '${_shorten(accountName!)} (مؤرشف)' : _shorten(accountName!),
                  background: neutralBadgeBackground,
                  foreground: neutralBadgeForeground,
                ),
              if (isAuto)
                _MiniBadge(
                  icon: Icons.auto_awesome,
                  label: confidence != null
                      ? 'تصنيف تلقائي ${(confidence * 100).round()}%'
                      : 'تصنيف تلقائي',
                  background: autoBadgeBackground,
                  foreground: autoBadgeForeground,
                ),
              if (transaction.category == null)
                _MiniBadge(
                  icon: Icons.label_off_outlined,
                  label: 'بدون تصنيف',
                  background: uncategorizedBadgeBackground,
                  foreground: uncategorizedBadgeForeground,
                ),
            ],
          ),
        ],
      ),
      // قارئ الشاشة بيقرا "دخل 4.5 دينار" بدل "+4.5"، والإشارة +/- مكتوبة بالنص (مش اللون وحده)
      trailing: Semantics(
        label: '${isIncome ? 'دخل' : 'مصروف'} ${transaction.amount.toStringAsFixed(1)} دينار',
        excludeSemantics: true,
        child: Text(
          '$amountPrefix${transaction.amount.toStringAsFixed(1)}',
          style: TextStyle(color: amountColor, fontWeight: FontWeight.bold, fontSize: 15),
        ),
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
          Flexible(child: Text(label, style: TextStyle(fontSize: 12, color: foreground))),
        ],
      ),
    );
  }
}
