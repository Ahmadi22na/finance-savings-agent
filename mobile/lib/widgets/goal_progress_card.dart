import 'package:flutter/material.dart';

import '../models/goal.dart';
import '../theme/icon_mapper.dart';

class GoalProgressCard extends StatelessWidget {
  final Goal goal;
  final Color accentColor;

  const GoalProgressCard({super.key, required this.goal, required this.accentColor});

  @override
  Widget build(BuildContext context) {
    final isAchieved = goal.status == 'achieved';

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              CircleAvatar(
                backgroundColor: accentColor.withValues(alpha: 0.12),
                child: Icon(iconForKey(goal.icon), color: accentColor, size: 20),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Row(
                  children: [
                    Flexible(
                      child: Text(goal.title,
                          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                          overflow: TextOverflow.ellipsis),
                    ),
                    if (goal.isRecurring) ...[
                      const SizedBox(width: 6),


                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: accentColor.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.autorenew, size: 11, color: accentColor),
                            const SizedBox(width: 3),
                            Text('شهري',
                                style: TextStyle(
                                    fontSize: 10, color: accentColor, fontWeight: FontWeight.w600)),
                          ],
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              if (isAchieved)
                const Icon(Icons.celebration, color: Colors.amber)
              else
                Text('${goal.progressPercentage.toStringAsFixed(0)}%',
                    style: TextStyle(color: accentColor, fontWeight: FontWeight.bold)),
            ],
          ),
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: LinearProgressIndicator(
              value: (goal.progressPercentage / 100).clamp(0.0, 1.0),
              minHeight: 8,
              backgroundColor: Colors.grey.shade200,
              color: isAchieved ? Colors.amber : accentColor,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '${goal.currentAmount.toStringAsFixed(0)} / ${goal.targetAmount.toStringAsFixed(0)} دينار',
            style: const TextStyle(fontSize: 12, color: Colors.black54),
          ),
        ],
      ),
    );
  }
}
