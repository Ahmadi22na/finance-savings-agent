/// يطابق app/schemas/goal.py -> GoalOut بالـ Backend.
class Goal {
  final String id;
  final String title;
  final String icon;
  final double targetAmount;
  final double currentAmount;
  final DateTime? deadline;
  final String status; // active | achieved | abandoned
  final double progressPercentage;

  Goal({
    required this.id,
    required this.title,
    required this.icon,
    required this.targetAmount,
    required this.currentAmount,
    required this.deadline,
    required this.status,
    required this.progressPercentage,
  });

  factory Goal.fromJson(Map<String, dynamic> json) {
    return Goal(
      id: json['id'] as String,
      title: json['title'] as String,
      icon: json['icon'] as String,
      targetAmount: (json['target_amount'] as num).toDouble(),
      currentAmount: (json['current_amount'] as num).toDouble(),
      deadline: json['deadline'] != null ? DateTime.parse(json['deadline'] as String) : null,
      status: json['status'] as String,
      progressPercentage: (json['progress_percentage'] as num).toDouble(),
    );
  }
}
