import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../core/api_client.dart';
import '../core/dashboard_providers.dart';
import '../core/providers.dart';
import '../models/transaction.dart';
import '../theme/app_theme.dart';

/// ورقة سفلية لتعديل مبلغ معاملة وملاحظتها وتاريخها. بترجّع true إذا انحفظ تعديل فعلاً.
/// بنرسل للسيرفر بس الحقول اللي تغيّرت. (دخل موزَّع على أهداف: السيرفر بيرفض مبلغًا أقل من الموزَّع منه ويرجّع السبب.)
Future<bool?> showTransactionEditSheet(BuildContext context, Transaction transaction) {
  return showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => _TransactionEditSheet(transaction: transaction),
  );
}

class _TransactionEditSheet extends ConsumerStatefulWidget {
  final Transaction transaction;

  const _TransactionEditSheet({required this.transaction});

  @override
  ConsumerState<_TransactionEditSheet> createState() => _TransactionEditSheetState();
}

class _TransactionEditSheetState extends ConsumerState<_TransactionEditSheet> {
  late final TextEditingController _amountController;
  late final TextEditingController _noteController;
  late DateTime _occurredAt;
  bool _isSaving = false;
  String? _amountError;

  @override
  void initState() {
    super.initState();
    final transaction = widget.transaction;
    _amountController = TextEditingController(text: _formatAmount(transaction.amount));
    _noteController = TextEditingController(text: transaction.note ?? '');
    _occurredAt = transaction.occurredAt.toLocal();
  }

  @override
  void dispose() {
    _amountController.dispose();
    _noteController.dispose();
    super.dispose();
  }

  static String _formatAmount(double value) {
    if (value == value.roundToDouble()) return value.toStringAsFixed(0);
    return value.toStringAsFixed(3).replaceFirst(RegExp(r'0+$'), '');
  }

  /// يقبل أرقام عربية وفاصلة عربية/إنجليزية، وحتى 3 خانات عشرية (فلس). بيرجّع null إذا مش صالح.
  static double? parseAmount(String raw) {
    var text = raw.trim();
    const arabicDigits = '٠١٢٣٤٥٦٧٨٩';
    for (var i = 0; i < arabicDigits.length; i++) {
      text = text.replaceAll(arabicDigits[i], '$i');
    }
    text = text.replaceAll('٫', '.').replaceAll('،', '.').replaceAll(',', '.');
    if (!RegExp(r'^\d+(\.\d{1,3})?$').hasMatch(text)) return null;
    final value = double.parse(text);
    return value > 0 ? value : null;
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _occurredAt,
      firstDate: DateTime(2020),
      lastDate: DateTime.now().add(const Duration(days: 1)),
    );
    if (picked == null) return;
    setState(() {
      _occurredAt = DateTime(picked.year, picked.month, picked.day, _occurredAt.hour, _occurredAt.minute);
    });
  }

  Future<void> _save() async {
    final transaction = widget.transaction;
    final amount = parseAmount(_amountController.text);
    if (amount == null) {
      setState(() => _amountError = 'اكتب مبلغًا صحيحًا أكبر من صفر (حتى 3 خانات عشرية)');
      return;
    }
    setState(() => _amountError = null);

    final amountChanged = (amount - transaction.amount).abs() > 0.0004;
    final newNote = _noteController.text.trim();
    final noteChanged = newNote != (transaction.note ?? '').trim();
    final dateChanged = !_occurredAt.isAtSameMomentAs(transaction.occurredAt);

    if (!amountChanged && !noteChanged && !dateChanged) {
      Navigator.of(context).pop(false);
      return;
    }

    final messenger = ScaffoldMessenger.of(context);
    setState(() => _isSaving = true);
    try {
      await ref.read(transactionServiceProvider).updateTransaction(
            transaction.id,
            amount: amountChanged ? amount : null,
            note: noteChanged && newNote.isNotEmpty ? newNote : null,
            clearNote: noteChanged && newNote.isEmpty,
            occurredAt: dateChanged ? _occurredAt : null,
          );
      ref.invalidate(recentTransactionsProvider);
      if (!mounted) return;
      Navigator.of(context).pop(true);
      messenger.showSnackBar(const SnackBar(content: Text('تم تعديل المعاملة ✅')));
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _isSaving = false);
      messenger.showSnackBar(SnackBar(content: Text(e.message)));
    } catch (_) {
      if (!mounted) return;
      setState(() => _isSaving = false);
      messenger.showSnackBar(const SnackBar(content: Text('ما قدرنا نحفظ التعديل، جرب كمان شوي')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('تعديل المعاملة', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 16),
              TextField(
                controller: _amountController,
                enabled: !_isSaving,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: InputDecoration(
                  labelText: 'المبلغ (دينار)',
                  errorText: _amountError,
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _noteController,
                enabled: !_isSaving,
                maxLength: 200,
                decoration: const InputDecoration(labelText: 'ملاحظة'),
              ),
              const SizedBox(height: 4),
              Row(
                children: [
                  const Icon(Icons.event_outlined, size: 18, color: AppColors.secondaryText),
                  const SizedBox(width: 8),
                  Expanded(child: Text(DateFormat('d/M/yyyy - HH:mm').format(_occurredAt))),
                  TextButton(
                    onPressed: _isSaving ? null : _pickDate,
                    child: const Text('غيّر التاريخ'),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: _isSaving ? null : _save,
                  child: _isSaving
                      ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Text('حفظ'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
