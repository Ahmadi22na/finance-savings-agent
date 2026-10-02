import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../core/dashboard_providers.dart';
import '../../models/goal.dart';
import '../../theme/app_theme.dart';




///





class GoalPathScreen extends ConsumerStatefulWidget {
  final Goal goal;
  const GoalPathScreen({super.key, required this.goal});

  @override
  ConsumerState<GoalPathScreen> createState() => _GoalPathScreenState();
}

class _GoalPathScreenState extends ConsumerState<GoalPathScreen> {
  static const int stageCount = 10;
  static const double _nodeSize = 56;
  static const double _verticalGap = 90;
  bool _isDeleting = false;

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(currentUserProvider);
    final accentColor =
        user?.persona != null ? PersonaColors.fromKey(user!.persona!.key) : PersonaColors.energetic;

    final completedStages = _completedStagesCount();
    final scheduleInfo = _scheduleStatus();
    final pathWidth = MediaQuery.of(context).size.width - 40;
    final pathHeight = (stageCount - 1) * _verticalGap + _nodeSize + 20;

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.goal.title),
        actions: [
          IconButton(
            icon: const Icon(Icons.delete_outline),
            onPressed: _isDeleting ? null : () => _confirmDelete(context),
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                Text(
                  '${widget.goal.currentAmount.toStringAsFixed(0)} / ${widget.goal.targetAmount.toStringAsFixed(0)} دينار',
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
            child: SingleChildScrollView(
              reverse: true,
              padding: const EdgeInsets.symmetric(vertical: 24),
              child: SizedBox(
                width: pathWidth,
                height: pathHeight,
                child: Stack(
                  children: [

                    CustomPaint(
                      size: Size(pathWidth, pathHeight),
                      painter: _PathPainter(
                        stageCount: stageCount,
                        completedStages: completedStages,
                        nodeSize: _nodeSize,
                        verticalGap: _verticalGap,
                        pathWidth: pathWidth,
                        accentColor: accentColor,
                      ),
                    ),
                    for (int stageNumber = 1; stageNumber <= stageCount; stageNumber++)
                      Positioned(
                        left: _xPositionFor(stageNumber, pathWidth),
                        bottom: (stageNumber - 1) * _verticalGap,
                        child: _StageNode(
                          stageNumber: stageNumber,
                          isCompleted: stageNumber <= completedStages,
                          isCurrent: stageNumber == completedStages + 1,
                          accentColor: accentColor,
                          size: _nodeSize,
                          onTap: stageNumber <= completedStages
                              ? () => _showStageMessage(context, stageNumber)
                              : null,
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }



  double _xPositionFor(int stageNumber, double pathWidth) {
    final isLeftSide = stageNumber.isOdd;
    return isLeftSide ? 0 : (pathWidth - _nodeSize);
  }

  int _completedStagesCount() {
    if (widget.goal.targetAmount <= 0) return 0;
    final ratio = widget.goal.currentAmount / widget.goal.targetAmount;
    return (ratio * stageCount).floor().clamp(0, stageCount);
  }

  _ScheduleInfo? _scheduleStatus() {
    if (widget.goal.deadline == null) return null;

    final totalDays = widget.goal.deadline!.difference(widget.goal.createdAt).inDays;
    if (totalDays <= 0) return null;

    final elapsedDays = DateTime.now().difference(widget.goal.createdAt).inDays.clamp(0, totalDays);
    final expectedStage = ((elapsedDays / totalDays) * stageCount).floor().clamp(0, stageCount);
    final actualStage = _completedStagesCount();
    final onTrack = actualStage >= expectedStage;

    return _ScheduleInfo(
      onTrack: onTrack,
      label: onTrack ? 'ماشي حسب الخطة 👍' : 'متأخر شوي عن الجدول الزمني ⏰',
    );
  }

  void _showStageMessage(BuildContext context, int stageNumber) {
    const messages = [
      'بداية قوية! 🚀', 'ماشي منيح تابع! 💪', 'ربع الطريق خلص! 🎯', 'استمر، شكلك جاد! 🔥',
      'نص الطريق! هاي لحظة تستاهل وقفة 🎉', 'تجاوزت النص، الباقي أسهل 😎', 'قريب أكتر من بعيد هلأ ⭐',
      'كمان شوي ووصلت! 🏁', 'أنت عمليًا وصلت! 🙌', 'مبروك! هيك بيكون التوفير 🏆',
    ];
    final index = (stageNumber - 1).clamp(0, messages.length - 1);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(messages[index]), duration: const Duration(seconds: 2)),
    );
  }

  Future<void> _confirmDelete(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('حذف الهدف؟'),
        content: Text('رح تحذف "${widget.goal.title}" نهائيًا. هاد الإجراء ما بينرجع.'),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('إلغاء')),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('حذف', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;

    setState(() => _isDeleting = true);
    try {
      final goalService = ref.read(goalServiceProvider);
      await goalService.deleteGoal(widget.goal.id);
      ref.invalidate(goalsListProvider);
      if (context.mounted) Navigator.of(context).pop();
    } catch (e) {
      if (context.mounted) {
        setState(() => _isDeleting = false);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('ما قدرنا نحذف الهدف، جرب كمان شوي')),
        );
      }
    }
  }
}

class _ScheduleInfo {
  final bool onTrack;
  final String label;
  _ScheduleInfo({required this.onTrack, required this.label});
}




class _PathPainter extends CustomPainter {
  final int stageCount;
  final int completedStages;
  final double nodeSize;
  final double verticalGap;
  final double pathWidth;
  final Color accentColor;

  _PathPainter({
    required this.stageCount,
    required this.completedStages,
    required this.nodeSize,
    required this.verticalGap,
    required this.pathWidth,
    required this.accentColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final incompletePaint = Paint()
      ..color = Colors.grey.shade300
      ..strokeWidth = 5
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    final completePaint = Paint()
      ..color = accentColor
      ..strokeWidth = 5
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    Offset centerOf(int stageNumber) {
      final isLeftSide = stageNumber.isOdd;
      final x = (isLeftSide ? 0 : (pathWidth - nodeSize)) + nodeSize / 2;
      final yFromBottom = (stageNumber - 1) * verticalGap + nodeSize / 2;
      final y = size.height - yFromBottom;
      return Offset(x, y);
    }

    for (int stageNumber = 1; stageNumber < stageCount; stageNumber++) {
      final start = centerOf(stageNumber);
      final end = centerOf(stageNumber + 1);
      final isSegmentCompleted = stageNumber < completedStages;

      final path = Path()
        ..moveTo(start.dx, start.dy)
        ..cubicTo(start.dx, start.dy - verticalGap / 2, end.dx, end.dy + verticalGap / 2, end.dx, end.dy);

      canvas.drawPath(path, isSegmentCompleted ? completePaint : incompletePaint);
    }
  }

  @override
  bool shouldRepaint(covariant _PathPainter oldDelegate) {
    return oldDelegate.completedStages != completedStages || oldDelegate.accentColor != accentColor;
  }
}

class _StageNode extends StatelessWidget {
  final int stageNumber;
  final bool isCompleted;
  final bool isCurrent;
  final Color accentColor;
  final double size;
  final VoidCallback? onTap;

  const _StageNode({
    required this.stageNumber,
    required this.isCompleted,
    required this.isCurrent,
    required this.accentColor,
    required this.size,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final borderColor = isCurrent || isCompleted ? accentColor : Colors.grey.shade300;

    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: isCompleted ? accentColor : Colors.white,
          border: Border.all(color: borderColor, width: isCurrent ? 3 : 2),
          boxShadow: [
            BoxShadow(
              color: isCurrent ? accentColor.withValues(alpha: 0.35) : Colors.black12,
              blurRadius: isCurrent ? 10 : 4,
              spreadRadius: isCurrent ? 2 : 0,
            ),
          ],
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
