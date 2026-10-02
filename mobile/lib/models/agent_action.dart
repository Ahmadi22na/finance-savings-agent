
class AgentAction {
  final String id;
  final String actionType; // suggest_category_correction | suggest_goal_contribution
  final String status; // pending | applied | rejected
  final Map<String, dynamic> payload;
  final String? reasoning;

  AgentAction({
    required this.id,
    required this.actionType,
    required this.status,
    required this.payload,
    required this.reasoning,
  });

  factory AgentAction.fromJson(Map<String, dynamic> json) {
    return AgentAction(
      id: json['id'] as String,
      actionType: json['action_type'] as String,
      status: json['status'] as String,
      payload: Map<String, dynamic>.from(json['payload'] as Map),
      reasoning: json['reasoning'] as String?,
    );
  }
}
