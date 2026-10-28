import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../core/account_format.dart';
import '../core/api_client.dart';
import '../core/dashboard_providers.dart';
import '../core/financial_account_providers.dart';
import '../core/providers.dart';
import '../models/financial_account.dart';
import '../theme/app_theme.dart';

/// ورقة تحويل بين حسابين نشطين للمستخدم. بترجّع true إذا انعمل التحويل.
/// التحويل مش دخل ولا مصروف: السيرفر بينشئ طرفين بعملية ذرّية وبيحرّك رصيدي الحسابين.
Future<bool?> showTransferSheet(BuildContext context) {
  return showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => const _TransferSheet(),
  );
}

class _TransferSheet extends ConsumerStatefulWidget {
  const _TransferSheet();

  @override
  ConsumerState<_TransferSheet> createState() => _TransferSheetState();
}

class _TransferSheetState extends ConsumerState<_TransferSheet> {
  final TextEditingController _amountController = TextEditingController();
  final TextEditingController _noteController = TextEditingController();
  String? _fromId;
  String? _toId;
  DateTime? _occurredAt; // null = "الآن" (السيرفر بيحط الوقت)
  bool _saving = false;
  String? _accountsError;
  String? _amountError;
  String? _error;

  @override
  void dispose() {
    _amountController.dispose();
    _noteController.dispose();
    super.dispose();
  }

  Future<void> _pickDateTime() async {
    final now = DateTime.now();
    final date = await showDatePicker(
      context: context,
      initialDate: _occurredAt ?? now,
      firstDate: DateTime(2020),
      lastDate: now,
    );
    if (date == null || !mounted) return;
    final time = await showTimePicker(context: context, initialTime: TimeOfDay.fromDateTime(_occurredAt ?? now));
    if (time == null || !mounted) return;
    final picked = DateTime(date.year, date.month, date.day, time.hour, time.minute);
    if (picked.isAfter(now)) {
      setState(() => _error = 'وقت التحويل ما بيصير يكون بالمستقبل');
      return;
    }
    setState(() {
      _occurredAt = picked;
      _error = null;
    });
  }

  Future<void> _save() async {
    String? accountsError;
    String? amountError;

    if (_fromId == null || _toId == null) {
      accountsError = 'اختار الحساب المحوَّل منه والمحوَّل إليه';
    } else if (_fromId == _toId) {
      accountsError = 'ما بتقدر تحوّل من حساب لنفسه';
    }

    final parsed = parseSignedMoney(_amountController.text);
    double? amount;
    if (parsed.error != null) {
      amountError = parsed.error;
    } else if (parsed.value! <= 0) {
      amountError = 'مبلغ التحويل لازم يكون أكبر من صفر';
    } else {
      amount = parsed.value;
    }

    if (accountsError != null || amountError != null) {
      setState(() {
        _accountsError = accountsError;
        _amountError = amountError;
      });
      return;
    }

    setState(() {
      _accountsError = null;
      _amountError = null;
      _error = null;
      _saving = true;
    });
    try {
      await ref.read(financialAccountServiceProvider).createTransfer(
            fromAccountId: _fromId!,
            toAccountId: _toId!,
            amount: amount!,
            note: _noteController.text,
            occurredAt: _occurredAt,
          );
      ref.invalidate(recentTransactionsProvider);
      refreshFinancialAccounts(ref);
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

  Widget _accountChips({
    required String label,
    required List<FinancialAccount> accounts,
    required String? selectedId,
    required String? disabledId,
    required ValueChanged<String> onSelected,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontWeight: FontWeight.bold)),
        const SizedBox(height: 6),
        Wrap(
          spacing: 8,
          runSpacing: 4,
          children: [
            for (final account in accounts)
              ChoiceChip(
                label: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 180),
                  child: Text(account.name, maxLines: 1, overflow: TextOverflow.ellipsis),
                ),
                selected: selectedId == account.id,
                onSelected: (_saving || account.id == disabledId) ? null : (_) => onSelected(account.id),
              ),
          ],
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final accountsAsync = ref.watch(activeAccountsProvider);

    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
          child: accountsAsync.when(
            loading: () => const SizedBox(height: 120, child: Center(child: CircularProgressIndicator())),
            error: (error, _) => Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(error is ApiException ? error.message : 'صار خطأ غير متوقع، جرب كمان شوي', textAlign: TextAlign.center),
                const SizedBox(height: 12),
                OutlinedButton(
                  onPressed: () => ref.invalidate(activeAccountsProvider),
                  child: const Text('إعادة المحاولة'),
                ),
              ],
            ),
            data: (accounts) {
              if (accounts.length < 2) {
                return const Padding(
                  padding: EdgeInsets.symmetric(vertical: 24),
                  child: Text('لازم يكون عندك حسابين مفعّلين على الأقل عشان تعمل تحويل.', textAlign: TextAlign.center),
                );
              }
              return Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('تحويل بين حسابين', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 4),
                  const Text(
                    'التحويل مش دخل ولا مصروف: بينقص من حساب وبيزيد على الثاني، وما بيأثر على أهدافك ولا على تقدير مصاريفك.',
                    style: TextStyle(fontSize: 12, color: AppColors.secondaryText),
                  ),
                  const SizedBox(height: 16),
                  _accountChips(
                    label: 'من حساب',
                    accounts: accounts,
                    selectedId: _fromId,
                    disabledId: _toId,
                    onSelected: (id) => setState(() => _fromId = id),
                  ),
                  const SizedBox(height: 12),
                  _accountChips(
                    label: 'إلى حساب',
                    accounts: accounts,
                    selectedId: _toId,
                    disabledId: _fromId,
                    onSelected: (id) => setState(() => _toId = id),
                  ),
                  if (_accountsError != null) ...[
                    const SizedBox(height: 8),
                    Text(_accountsError!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                  ],
                  const SizedBox(height: 16),
                  TextField(
                    controller: _amountController,
                    enabled: !_saving,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    decoration: InputDecoration(labelText: 'المبلغ بالدينار', errorText: _amountError),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _noteController,
                    enabled: !_saving,
                    maxLength: 200,
                    decoration: const InputDecoration(labelText: 'ملاحظة (اختياري)'),
                  ),
                  Row(
                    children: [
                      const Icon(Icons.event_outlined, size: 18, color: AppColors.secondaryText),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(_occurredAt == null
                            ? 'وقت التحويل: الآن'
                            : 'وقت التحويل: ${DateFormat('d/M/yyyy - HH:mm').format(_occurredAt!)}'),
                      ),
                      TextButton(
                        onPressed: _saving ? null : _pickDateTime,
                        child: const Text('غيّر الوقت'),
                      ),
                    ],
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 8),
                    Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                  ],
                  const SizedBox(height: 12),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      onPressed: _saving ? null : _save,
                      child: _saving
                          ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                          : const Text('حوّل'),
                    ),
                  ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }
}
