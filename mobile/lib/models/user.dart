import 'persona.dart';

class AppUser {
  final String id;
  final String name;
  final String phone;
  final String incomeType;
  final String agentName;
  final bool hasCompletedOnboarding;
  final Persona? persona;

  AppUser({
    required this.id,
    required this.name,
    required this.phone,
    required this.incomeType,
    required this.agentName,
    required this.hasCompletedOnboarding,
    this.persona,
  });

  factory AppUser.fromJson(Map<String, dynamic> json) {
    return AppUser(
      id: json['id'] as String,
      name: json['name'] as String,
      phone: json['phone'] as String,
      incomeType: json['income_type'] as String,
      agentName: json['agent_name'] as String,
      hasCompletedOnboarding: json['has_completed_onboarding'] as bool,
      persona: json['persona'] != null
          ? Persona.fromJson(json['persona'] as Map<String, dynamic>)
          : null,
    );
  }
}
