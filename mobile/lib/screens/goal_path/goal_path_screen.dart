import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../models/goal.dart';
import '../../theme/app_theme.dart';

/// شاشة "طريق الهدف" — شكل ثابت دايمًا (10 مراحل بنفس التخطيط)، بس محتواه
/// (كم مرحلة مكتملة، وهل ماشي حسب الجدول الزمني) مبني على بيانات هدف
/// المستخدم الفعلية. المراحل مبنية على المبلغ *والوقت* سوا لو الهدف عنده
/// Deadline — هيك المستخدم بيعرف فعليًا هل هو "ماشي صح" مش بس "كم وفر".
class GoalPathScreen extends ConsumerWidget {
  final Goal goal;
  const GoalPathScreen({super.key, required this.goal});

  static const int stageCount = 10;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);
    final accentColor =
        user?.persona != null ? PersonaColors.fromKey(user!.persona!.key) : PersonaColors.energetic;

    final completedStages = _completedStagesCount();
    final scheduleInfo = _scheduleStatus();

    return Scaffold(
      appBar: AppBar(title: Text(goal.title)),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                Text(
                  '${goal.currentAmount.toStringAsFixed(0)} / ${goal.targetAmount.toStringAsFixed(0)} دينار',
                  style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                ),
                if (scheduleInfo != null) ...[
                  const SizedBox(height: 10),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                    decoration: BoxDecoration(
                      color: scheduleInfo.onTrack ? Colors.green.shade50 : Colors.orange.shade50,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(
                      scheduleInfo.label,
                      style: TextStyle(
                        color: scheduleInfo.onTrack ? Colors.green.shade800 : Colors.orange.shade800,
                        fontWeight: FontWeight.w600,
                        fontSize: 12,
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
          Expanded(
            child: ListView.builder(
              reverse: true, // نبلش من تحت (مرحلة 1) ونطلع فوق (الهدف) — إحساس "تسلّق" للأعلى
              padding: const EdgeInsets.symmetric(vertical: 24, horizontal: 20),
              itemCount: stageCount,
              itemBuilder: (context, indexFromBottom) {
                final stageNumber = indexFromBottom + 1; // 1..10
                final isCompleted = stageNumber <= completedStages;
                final isCurrent = stageNumber == completedStages + 1;
                final alignRight = stageNumber.isOdd; // تعرّج ثابت — نفس الشكل دايمًا بغض النظر عن الهدف

                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  child: Row(
                    mainAxisAlignment: alignRight ? MainAxisAlignment.end : MainAxisAlignment.start,
                    children: [
                      _StageNode(
                        stageNumber: stageNumber,
                        isCompleted: isCompleted,
                        isCurrent: isCurrent,
                        accentColor: accentColor,
                        onTap: isCompleted ? () => _showStageMessage(context, stageNumber) : null,
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  int _completedStagesCount() {
    if (goal.targetAmount <= 0) return 0;
    final ratio = goal.currentAmount / goal.targetAmount;
    return (ratio * stageCount).floor().clamp(0, stageCount);
  }

  _ScheduleInfo? _scheduleStatus() {
    if (goal.deadline == null) return null;

    final totalDays = goal.deadline!.difference(goal.createdAt).inDays;
    if (totalDays <= 0) return null; // بيانات غير منطقية (Deadline بالماضي) — نتجاهل بهدوء

    final elapsedDays = DateTime.now().difference(goal.createdAt).inDays.clamp(0, totalDays);
    final expectedStage = ((elapsedDays / totalDays) * stageCount).floor().clamp(0, stageCount);
    final actualStage = _completedStagesCount();
    final onTrack = actualStage >= expectedStage;

    return _ScheduleInfo(
      onTrack: onTrack,
      label: onTrack ? 'ماشي حسب الخطة 👍' : 'متأخر شوي عن الجدول الزمني ⏰',
    );
  }

  void _showStageMessage(BuildContext context, int stageNumber) {
    // رسائل ثابتة بسيطة — مش من رشيد فعليًا (بدون أي استدعاء AI)، بس كافية
    // تعطي إحساس الاحتفال بكل مرحلة بدون أي تكلفة إضافية
    const messages = [
      'بداية قوية! 🚀',
      'ماشي منيح تابع! 💪',
      'ربع الطريق خلص! 🎯',
      'استمر، شكلك جاد! 🔥',
      'نص الطريق! هاي لحظة تستاهل وقفة 🎉',
      'تجاوزت النص، الباقي أسهل 😎',
      'قريب أكتر من بعيد هلأ ⭐',
      'كمان شوي ووصلت! 🏁',
      'أنت عمليًا وصلت! 🙌',
      'مبروك! هيك بيكون التوفير 🏆',
    ];
    final index = (stageNumber - 1).clamp(0, messages.length - 1);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(messages[index]), duration: const Duration(seconds: 2)),
    );
  }
}

class _ScheduleInfo {
  final bool onTrack;
  final String label;
  _ScheduleInfo({required this.onTrack, required this.label});
}

class _StageNode extends StatelessWidget {
  final int stageNumber;
  final bool isCompleted;
  final bool isCurrent;
  final Color accentColor;
  final VoidCallback? onTap;

  const _StageNode({
    required this.stageNumber,
    required this.isCompleted,
    required this.isCurrent,
    required this.accentColor,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final borderColor = isCurrent ? accentColor : (isCompleted ? accentColor : Colors.grey.shade300);

    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 56,
        height: 56,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: isCompleted ? accentColor : Colors.white,
          border: Border.all(color: borderColor, width: isCurrent ? 3 : 2),
          boxShadow: isCurrent
              ? [BoxShadow(color: accentColor.withValues(alpha: 0.35), blurRadius: 10, spreadRadius: 2)]
              : null,
        ),
        child: Center(
          child: isCompleted
              ? const Icon(Icons.check, color: Colors.white)
              : Text(
                  '$stageNumber',
                  style: TextStyle(color: Colors.grey.shade500, fontWeight: FontWeight.bold),
                ),
        ),
      ),
    );
  }
}
