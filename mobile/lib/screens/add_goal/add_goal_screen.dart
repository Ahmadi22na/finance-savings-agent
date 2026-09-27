import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../core/dashboard_providers.dart';
import '../../core/api_client.dart';
import '../../widgets/app_text_field.dart';

/// شاشة إضافة هدف يدويًا — الفجوة يلي اكتشفناها بـ Sprint 7: قبل هالشاشة
/// ما كانت في طريقة تضيف هدف إلا عن طريق الـ Onboarding (أول هدف بس) أو
/// اقتراح رشيد بالشات. نفس الحقول بالضبط يلي يبنيها الشات (عنوان، مبلغ،
/// موعد اختياري، مصروف ثابت شهري) — القيمة المضافة هون إنك تقدر تضيفها
/// مباشرة بدون ما تحتاج تحكي لرشيد كل مرة.
class AddGoalScreen extends ConsumerStatefulWidget {
  const AddGoalScreen({super.key});

  @override
  ConsumerState<AddGoalScreen> createState() => _AddGoalScreenState();
}

class _AddGoalScreenState extends ConsumerState<AddGoalScreen> {
  final _formKey = GlobalKey<FormState>();
  final _titleController = TextEditingController();
  final _amountController = TextEditingController();
  DateTime? _deadline;
  bool _isRecurring = false;
  bool _isSubmitting = false;
  String? _error;

  @override
  void dispose() {
    _titleController.dispose();
    _amountController.dispose();
    super.dispose();
  }

  Future<void> _pickDeadline() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: DateTime.now().add(const Duration(days: 30)),
      firstDate: DateTime.now(),
      lastDate: DateTime.now().add(const Duration(days: 365 * 3)),
    );
    if (picked != null) setState(() => _deadline = picked);
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isSubmitting = true;
      _error = null;
    });
    try {
      await ref.read(goalServiceProvider).createGoal(
            title: _titleController.text.trim(),
            targetAmount: double.parse(_amountController.text.trim()),
            deadline: _deadline,
            isRecurring: _isRecurring,
          );
      ref.invalidate(goalsListProvider);
      if (mounted) Navigator.of(context).pop();
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _isSubmitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('هدف جديد')),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Form(
          key: _formKey,
          child: ListView(
            children: [
              AppTextField(
                controller: _titleController,
                label: 'اسم الهدف',
                validator: (value) {
                  if (value == null || value.trim().length < 2) {
                    return 'لازم حرفين على الأقل';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 16),
              AppTextField(
                controller: _amountController,
                label: 'المبلغ المستهدف (دينار)',
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                validator: (value) {
                  final parsed = double.tryParse((value ?? '').trim());
                  if (parsed == null || parsed <= 0) return 'أدخل مبلغ صحيح أكبر من صفر';
                  return null;
                },
              ),
              const SizedBox(height: 16),
              // موعد اختياري — GoalPathScreen يستخدمه لحساب "هل انت متأخر عن
              // الجدول" لو موجود، مش إلزامي لإنشاء الهدف
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(_deadline == null
                    ? 'موعد نهائي (اختياري)'
                    : 'الموعد: ${_deadline!.year}/${_deadline!.month}/${_deadline!.day}'),
                trailing: TextButton(
                  onPressed: _pickDeadline,
                  child: Text(_deadline == null ? 'حدد' : 'غيّر'),
                ),
              ),
              const Divider(),
              // "مصروف ثابت شهري" — نفس الخطة بالضبط بقاعدة البيانات، الفرق
              // الوحيد إنها بتتصفّر تلقائيًا كل شهر لما توصل لهدفها (Lazy
              // Reset بالباكيند) بدل ما تضل "منجزة" للأبد.
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                value: _isRecurring,
                onChanged: (value) => setState(() => _isRecurring = value),
                title: const Text('مصروف ثابت شهري'),
                subtitle: const Text(
                  'زي إيجار أو اشتراك — بتتصفّر تلقائيًا كل شهر بعد ما توصل لهدفها',
                  style: TextStyle(fontSize: 12),
                ),
                secondary: const Icon(Icons.autorenew),
              ),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!, style: const TextStyle(color: Colors.red)),
              ],
              const SizedBox(height: 24),
              FilledButton(
                onPressed: _isSubmitting ? null : _submit,
                child: _isSubmitting
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : const Text('إنشاء الهدف'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
