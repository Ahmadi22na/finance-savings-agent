import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../core/account_format.dart';
import '../core/api_client.dart';
import '../core/providers.dart';
import '../models/financial_account.dart';
import '../theme/app_theme.dart';

/// ورقة "رصيدك هلأ كم؟": بتسجّل لقطة رصيد جديدة للحساب. بترجّع true إذا انحفظت.
/// الرقم بيصير نقطة البداية؛ السيرفر هو اللي بيحسب أثر المعاملات عليه (بدون أي حساب هون).
Future<bool?> showAccountBalanceSheet(BuildContext context, FinancialAccount account) {
  return showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => _AccountBalanceSheet(account: account),
  );
}

class _AccountBalanceSheet extends ConsumerStatefulWidget {
  final FinancialAccount account;

  const _AccountBalanceSheet({required this.account});

  @override
  ConsumerState<_AccountBalanceSheet> createState() => _AccountBalanceSheetState();
}

class _AccountBalanceSheetState extends ConsumerState<_AccountBalanceSheet> {
  final TextEditingController _amountController = TextEditingController();
  DateTime? _asOf; // null = "الآن" (السيرفر بيحط الوقت)
  bool _saving = false;
  String? _amountError;
  String? _error;

  @override
  void dispose() {
    _amountController.dispose();
    super.dispose();
  }

  Future<void> _pickDateTime() async {
    final now = DateTime.now();
    final date = await showDatePicker(
      context: context,
      initialDate: _asOf ?? now,
      firstDate: DateTime(2020),
      lastDate: now,
    );
    if (date == null || !mounted) return;
    final time = await showTimePicker(context: context, initialTime: TimeOfDay.fromDateTime(_asOf ?? now));
    if (time == null || !mounted) return;
    final picked = DateTime(date.year, date.month, date.day, time.hour, time.minute);
    if (picked.isAfter(now)) {
      setState(() => _error = 'وقت الرصيد ما بيصير يكون بالمستقبل');
      return;
    }
    setState(() {
      _asOf = picked;
      _error = null;
    });
  }

  Future<void> _save() async {
    final parsed = parseSignedMoney(_amountController.text);
    if (parsed.error != null) {
      setState(() => _amountError = parsed.error);
      return;
    }
    setState(() {
      _amountError = null;
      _error = null;
      _saving = true;
    });
    try {
      await ref.read(financialAccountServiceProvider).addBalance(
            widget.account.id,
            amount: parsed.value!,
            asOf: _asOf,
          );
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = e.message;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = 'صار خطأ غير متوقع، جرب كمان شوي';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final account = widget.account;
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('رصيدك هلأ كم؟ — ${account.name}',
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 16),
              TextField(
                controller: _amountController,
                enabled: !_saving,
                autofocus: true,
                keyboardType: const TextInputType.numberWithOptions(decimal: true, signed: true),
                decoration: InputDecoration(
                  labelText: 'رصيد الحساب الفعلي بالدينار',
                  helperText: account.balance == null
                      ? 'للسالب اكتب - قبل الرقم.'
                      : 'المعروض حاليًا: ${formatMoney(account.balance!)} دينار. للسالب اكتب - قبل الرقم.',
                  helperMaxLines: 2,
                  errorText: _amountError,
                ),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  const Icon(Icons.event_outlined, size: 18, color: AppColors.secondaryText),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(_asOf == null ? 'وقت الرصيد: الآن' : 'وقت الرصيد: ${DateFormat('d/M/yyyy - HH:mm').format(_asOf!)}'),
                  ),
                  TextButton(
                    onPressed: _saving ? null : _pickDateTime,
                    child: const Text('غيّر الوقت'),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              const Text(
                'هاد الرقم بيصير نقطة البداية: المعاملات المرتبطة بالحساب اللي وقتها بعده بتتحسب فوقه تلقائيًا، '
                'والمعاملات اللي وقتها قبله أو يساويه بتعتبر داخلة فيه.',
                style: TextStyle(fontSize: 12, color: AppColors.secondaryText),
              ),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
              ],
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: _saving ? null : _save,
                  child: _saving
                      ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Text('حفظ الرصيد'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
