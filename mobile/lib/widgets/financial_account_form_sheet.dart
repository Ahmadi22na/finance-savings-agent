import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/account_format.dart';
import '../core/api_client.dart';
import '../core/providers.dart';
import '../models/financial_account.dart';

/// ورقة إضافة حساب مالي أو تعديل اسمه ونوعه. بترجّع true إذا انحفظ تغيير فعلاً.
/// الرصيد الابتدائي اختياري وبس عند الإنشاء (بيتسجّل كلقطة رصيد بوقت الإنشاء)، وبعدها الرصيد بيتحدّث من "تحديث الرصيد".
Future<bool?> showFinancialAccountFormSheet(BuildContext context, {FinancialAccount? existing}) {
  return showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => _FinancialAccountFormSheet(existing: existing),
  );
}

class _FinancialAccountFormSheet extends ConsumerStatefulWidget {
  final FinancialAccount? existing;

  const _FinancialAccountFormSheet({this.existing});

  @override
  ConsumerState<_FinancialAccountFormSheet> createState() => _FinancialAccountFormSheetState();
}

class _FinancialAccountFormSheetState extends ConsumerState<_FinancialAccountFormSheet> {
  late final TextEditingController _nameController;
  final TextEditingController _openingController = TextEditingController();
  late String _kind;
  bool _saving = false;
  String? _nameError;
  String? _openingError;
  String? _error;

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController(text: widget.existing?.name ?? '');
    _kind = widget.existing?.kind ?? 'cash';
  }

  @override
  void dispose() {
    _nameController.dispose();
    _openingController.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final existing = widget.existing;
    final name = _nameController.text.trim();
    if (name.isEmpty) {
      setState(() => _nameError = 'اكتب اسم الحساب');
      return;
    }

    double? opening;
    if (existing == null && _openingController.text.trim().isNotEmpty) {
      final parsed = parseSignedMoney(_openingController.text);
      if (parsed.error != null) {
        setState(() {
          _nameError = null;
          _openingError = parsed.error;
        });
        return;
      }
      opening = parsed.value;
    }

    final nameChanged = existing != null && name != existing.name;
    final kindChanged = existing != null && _kind != existing.kind;
    if (existing != null && !nameChanged && !kindChanged) {
      Navigator.of(context).pop(false);
      return;
    }

    setState(() {
      _nameError = null;
      _openingError = null;
      _error = null;
      _saving = true;
    });
    final service = ref.read(financialAccountServiceProvider);
    try {
      if (existing == null) {
        await service.createAccount(name: name, kind: _kind, openingBalance: opening);
      } else {
        await service.updateAccount(
          existing.id,
          name: nameChanged ? name : null,
          kind: kindChanged ? _kind : null,
        );
      }
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
    final isEdit = widget.existing != null;
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(isEdit ? 'تعديل الحساب' : 'حساب مالي جديد',
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 16),
              TextField(
                controller: _nameController,
                enabled: !_saving,
                maxLength: 60,
                decoration: InputDecoration(labelText: 'اسم الحساب', errorText: _nameError),
              ),
              const SizedBox(height: 8),
              const Text('النوع'),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                children: [
                  for (final kind in const ['cash', 'bank', 'wallet'])
                    ChoiceChip(
                      label: Text(accountKindLabel(kind)),
                      selected: _kind == kind,
                      onSelected: _saving ? null : (_) => setState(() => _kind = kind),
                    ),
                ],
              ),
              if (!isEdit) ...[
                const SizedBox(height: 16),
                TextField(
                  controller: _openingController,
                  enabled: !_saving,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true, signed: true),
                  decoration: InputDecoration(
                    labelText: 'رصيدك الحالي بالدينار (اختياري)',
                    helperText: 'اتركه فاضي إذا ما بتعرفه — بيضل الرصيد "غير معروف". للسالب اكتب - قبل الرقم.',
                    helperMaxLines: 2,
                    errorText: _openingError,
                  ),
                ),
              ],
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
                      : Text(isEdit ? 'حفظ' : 'إضافة'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
