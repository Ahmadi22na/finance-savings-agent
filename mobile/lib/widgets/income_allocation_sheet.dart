import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/providers.dart';
import '../core/dashboard_providers.dart';
import '../core/api_client.dart';
import '../models/transaction.dart';
import '../models/goal.dart';

/// يفحص إذا معاملة الدخل هاي لسا فيها مبلغ غير موزّع، وإذا في خطط نشطة
/// أصلاً يقدر يوزع عليها — ولو نعم، بيفتح شاشة التوزيع مباشرة. يُستدعى من
/// كل نقطة ممكن ينضاف فيها دخل جديد (التسجيل السريع، وتأكيد اقتراح دخل من
/// الشات) عشان المستخدم دايمًا يُسأل "وين بدك تحط هالدخل؟" — هيك بالضبط
/// القرار المتفق عليه (دايمًا نسأل، ما في auto-route تلقائي).
Future<void> maybePromptIncomeAllocation(
  BuildContext context,
  WidgetRef ref,
  Transaction transaction,
) async {
  if (transaction.type != 'income' || transaction.unallocatedAmount <= 0) return;

  List<Goal> activeGoals;
  try {
    final allGoals = await ref.read(goalServiceProvider).listGoals();
    activeGoals = allGoals.where((g) => g.status == 'active').toList();
  } catch (_) {
    return; // فشل جلب الخطط مش شي حرج هون — بس ما نقدر نعرض الشاشة
  }

  // ما في خطط نشطة أصلاً (أو كلها متروكة/منجزة) — ما في وين نوزع، نتجاوز
  if (activeGoals.isEmpty || !context.mounted) return;

  await showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    builder: (_) => _IncomeAllocationSheet(
      callerContext: context,
      transaction: transaction,
      goals: activeGoals,
    ),
  );
}

class _IncomeAllocationSheet extends ConsumerStatefulWidget {
  final BuildContext callerContext;
  final Transaction transaction;
  final List<Goal> goals;
  const _IncomeAllocationSheet({
    required this.callerContext,
    required this.transaction,
    required this.goals,
  });

  @override
  ConsumerState<_IncomeAllocationSheet> createState() => _IncomeAllocationSheetState();
}

class _IncomeAllocationSheetState extends ConsumerState<_IncomeAllocationSheet> {
  late final Map<String, TextEditingController> _controllers;
  bool _isSubmitting = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _controllers = {for (final goal in widget.goals) goal.id: TextEditingController()};
    // تعبئة مسبقة: كامل المبلغ غير الموزّع على أعلى أولوية (أول خطة باللستة
    // — جاية أصلاً مرتبة حسب الأولوية من الباكيند) — المستخدم يقدر يعدّلها
    // ويوزّع على أكتر من خطة لو بدو.
    if (widget.goals.isNotEmpty) {
      _controllers[widget.goals.first.id]!.text = _formatAmount(widget.transaction.unallocatedAmount);
    }
  }

  @override
  void dispose() {
    for (final controller in _controllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  String _formatAmount(double value) {
    return value == value.roundToDouble() ? value.toStringAsFixed(0) : value.toStringAsFixed(2);
  }

  double get _totalEntered {
    double sum = 0;
    for (final controller in _controllers.values) {
      sum += double.tryParse(controller.text.trim()) ?? 0;
    }
    return sum;
  }

  Future<void> _submit() async {
    final allocations = <Map<String, dynamic>>[];
    for (final goal in widget.goals) {
      final value = double.tryParse(_controllers[goal.id]!.text.trim()) ?? 0;
      if (value > 0) allocations.add({'goal_id': goal.id, 'amount': value});
    }
    if (allocations.isEmpty) {
      setState(() => _error = 'حدد مبلغ لخطة وحدة على الأقل');
      return;
    }
    if (_totalEntered > widget.transaction.unallocatedAmount + 0.01) {
      setState(() => _error = 'مجموع المبالغ أكبر من الدخل المتاح');
      return;
    }

    setState(() {
      _isSubmitting = true;
      _error = null;
    });
    try {
      final updatedTransaction = await ref.read(transactionServiceProvider).allocateIncome(
            transactionId: widget.transaction.id,
            allocations: allocations,
          );
      ref.invalidate(goalsListProvider);
      ref.invalidate(recentTransactionsProvider);
      if (!mounted) return;
      Navigator.of(context).pop();

      // لو خطة وحدة أو أكتر اكتفت بأقل من المبلغ يلي حددته (مثلاً حطيت
      // 300 على هدف سقفه 150)، رشيد ما بيرمي الباقي — بيسألك فورًا وين
      // بدك تحطه، بنفس الشاشة، بس بآخر قيم الخطط (خطة اكتفت رح تختفي من
      // الخيارات لأنها صارت غير نشطة). لازم نستخدم Context الشاشة الأصلية
      // (يلي فتحت هالـ Sheet) مش Context الـ Sheet نفسه — هو صار Unmounted
      // فور ما استدعينا pop() فوق.
      if (updatedTransaction.unallocatedAmount > 0.01 && widget.callerContext.mounted) {
        await maybePromptIncomeAllocation(widget.callerContext, ref, updatedTransaction);
      }
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _isSubmitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final remaining = widget.transaction.unallocatedAmount - _totalEntered;

    return Padding(
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        top: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 20,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(
              width: 40, height: 4,
              margin: const EdgeInsets.only(bottom: 16),
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: Colors.black12,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            Text(
              'وين بدك تحط الـ ${_formatAmount(widget.transaction.unallocatedAmount)} دينار؟',
              style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 4),
            const Text(
              'قسّمهم على أكتر من خطة لو بدك — أي مبلغ ما توزعه بيضل بانتظارك',
              style: TextStyle(fontSize: 12, color: Colors.black45),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 20),
            ...widget.goals.map((goal) => Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: Row(
                    children: [
                      Expanded(
                        child: Row(
                          children: [
                            if (goal.isRecurring)
                              const Padding(
                                padding: EdgeInsets.only(left: 6),
                                child: Icon(Icons.autorenew, size: 14, color: Colors.black45),
                              ),
                            Flexible(
                              child: Text(goal.title, overflow: TextOverflow.ellipsis),
                            ),
                          ],
                        ),
                      ),
                      SizedBox(
                        width: 90,
                        child: TextField(
                          controller: _controllers[goal.id],
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                          textAlign: TextAlign.center,
                          decoration: const InputDecoration(isDense: true, suffixText: 'د'),
                          onChanged: (_) => setState(() {}),
                        ),
                      ),
                    ],
                  ),
                )),
            const SizedBox(height: 6),
            Text(
              remaining >= -0.01
                  ? 'المتبقي بدون توزيع: ${_formatAmount(remaining < 0 ? 0 : remaining)} دينار'
                  : 'تجاوزت المبلغ المتاح بـ ${_formatAmount(-remaining)} دينار',
              style: TextStyle(fontSize: 12, color: remaining < -0.01 ? Colors.red : Colors.black54),
            ),
            if (_error != null) ...[
              const SizedBox(height: 6),
              Text(_error!, style: const TextStyle(color: Colors.red, fontSize: 12)),
            ],
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: _isSubmitting ? null : () => Navigator.of(context).pop(),
                    child: const Text('لاحقًا'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: FilledButton(
                    onPressed: _isSubmitting ? null : _submit,
                    child: _isSubmitting
                        ? const SizedBox(
                            height: 18,
                            width: 18,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                          )
                        : const Text('وزّع'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
