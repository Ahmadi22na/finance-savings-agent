import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../core/account_format.dart';
import '../core/api_client.dart';
import '../core/dashboard_providers.dart';
import '../core/financial_account_providers.dart';
import '../core/providers.dart';
import '../core/transfer_grouping.dart';
import 'transaction_edit_sheet.dart';
import 'transaction_tile.dart';

/// سطر تحويل داخلي بقائمة المعاملات: طرفي الخروج والدخول مدموجين بسطر واحد، بمبلغ محايد (بدون + أو -).
/// التحويل مش دخل ولا مصروف حقيقي، وبنقول هيك صراحة بنص مش بلون وحده.
class TransferTile extends StatelessWidget {
  final TransferEntry entry;
  final String? fromName;
  final String? toName;
  final VoidCallback? onTap;

  const TransferTile({super.key, required this.entry, this.fromName, this.toName, this.onTap});

  String get _title {
    final from = fromName ?? 'حساب';
    final to = toName ?? 'حساب';
    if (entry.outLeg != null && entry.inLeg != null) return 'تحويل من $from إلى $to';
    if (entry.outLeg != null) return 'تحويل من $from';
    return 'تحويل إلى $to';
  }

  @override
  Widget build(BuildContext context) {
    final amountText = formatMoney(entry.amount);
    return ListTile(
      contentPadding: EdgeInsets.zero,
      onTap: onTap,
      leading: CircleAvatar(
        backgroundColor: Colors.grey.shade100,
        child: const Icon(Icons.swap_horiz, color: Color(0xFF212121), size: 20),
      ),
      title: Text(_title, style: const TextStyle(fontWeight: FontWeight.w600)),
      subtitle: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(DateFormat('d/M - HH:mm').format(entry.occurredAt), style: const TextStyle(fontSize: 12)),
          if (entry.note != null) Text(entry.note!, style: const TextStyle(fontSize: 12)),
          const SizedBox(height: 4),
          Wrap(
            spacing: 6,
            runSpacing: 4,
            children: [
              const _Tag(icon: Icons.swap_horiz, label: 'تحويل بين حساباتك — مش دخل ولا مصروف'),
              if (entry.isPartial) const _Tag(icon: Icons.info_outline, label: 'ظاهر بس طرف واحد من التحويل'),
            ],
          ),
        ],
      ),
      trailing: Semantics(
        label: 'تحويل $amountText دينار',
        excludeSemantics: true,
        child: Text(
          amountText,
          style: const TextStyle(color: TransactionTile.neutralBadgeForeground, fontWeight: FontWeight.bold, fontSize: 15),
        ),
      ),
    );
  }
}

class _Tag extends StatelessWidget {
  final IconData icon;
  final String label;

  const _Tag({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
      decoration: BoxDecoration(
        color: TransactionTile.neutralBadgeBackground,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: TransactionTile.neutralBadgeForeground),
          const SizedBox(width: 4),
          Flexible(
            child: Text(label, style: const TextStyle(fontSize: 12, color: TransactionTile.neutralBadgeForeground)),
          ),
        ],
      ),
    );
  }
}

/// ورقة إجراءات تحويل: تعديل المبلغ/الملاحظة/الوقت (السيرفر بيطبّقها على الطرفين)، أو حذف التحويل كامل.
/// ما في تصنيف ولا تغيير حسابات بالتحويل (لتغيير الحسابات: احذفه وأنشئه من جديد).
Future<void> showTransferActionsSheet(
  BuildContext context,
  TransferEntry entry, {
  String? fromName,
  String? toName,
}) {
  return showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    builder: (_) => _TransferActionsSheet(entry: entry, fromName: fromName, toName: toName),
  );
}

class _TransferActionsSheet extends ConsumerStatefulWidget {
  final TransferEntry entry;
  final String? fromName;
  final String? toName;

  const _TransferActionsSheet({required this.entry, this.fromName, this.toName});

  @override
  ConsumerState<_TransferActionsSheet> createState() => _TransferActionsSheetState();
}

class _TransferActionsSheetState extends ConsumerState<_TransferActionsSheet> {
  bool _busy = false;

  Future<void> _edit() async {
    final saved = await showTransactionEditSheet(context, widget.entry.anyLeg);
    if (saved == true && mounted) {
      refreshFinancialAccounts(ref); // المبلغ والتاريخ بيغيّروا رصيدي الحسابين
      Navigator.of(context).pop();
    }
  }

  Future<void> _delete() async {
    final from = widget.fromName ?? 'الحساب الأول';
    final to = widget.toName ?? 'الحساب الثاني';
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('حذف التحويل؟'),
        content: Text(
          'رح يتحذف التحويل كامل (طرف الخروج من $from وطرف الدخول إلى $to) وبترجع أرصدة الحسابين لما كانت قبله. '
          'ما بتقدر تتراجع.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(false), child: const Text('إلغاء')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: TransactionTile.expenseColor),
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('احذف'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    final messenger = ScaffoldMessenger.of(context);
    setState(() => _busy = true);
    try {
      await ref.read(transactionServiceProvider).deleteTransaction(widget.entry.anyLeg.id);
      ref.invalidate(recentTransactionsProvider);
      refreshFinancialAccounts(ref);
      if (!mounted) return;
      Navigator.of(context).pop();
      messenger.showSnackBar(const SnackBar(content: Text('تم حذف التحويل')));
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _busy = false);
      messenger.showSnackBar(SnackBar(content: Text(e.message)));
    } catch (_) {
      if (!mounted) return;
      setState(() => _busy = false);
      messenger.showSnackBar(const SnackBar(content: Text('ما قدرنا نحذف التحويل، جرب كمان شوي')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final entry = widget.entry;
    final title = entry.outLeg != null && entry.inLeg != null
        ? 'تحويل من ${widget.fromName ?? 'حساب'} إلى ${widget.toName ?? 'حساب'}'
        : 'تحويل بين حساباتك';
    return SafeArea(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          ListTile(
            leading: const Icon(Icons.swap_horiz),
            title: Text(title),
            subtitle: Text('${formatMoney(entry.amount)} دينار — مش دخل ولا مصروف'),
          ),
          const Divider(height: 1),
          ListTile(
            leading: const Icon(Icons.edit_outlined),
            title: const Text('تعديل المبلغ والملاحظة والتاريخ'),
            subtitle: const Text('بينطبق على طرفي التحويل'),
            enabled: !_busy,
            onTap: _edit,
          ),
          ListTile(
            leading: const Icon(Icons.delete_outline, color: TransactionTile.expenseColor),
            title: const Text('حذف التحويل', style: TextStyle(color: TransactionTile.expenseColor)),
            subtitle: const Text('بيحذف الطرفين وبيرجّع الأرصدة'),
            enabled: !_busy,
            onTap: _delete,
          ),
        ],
      ),
    );
  }
}
