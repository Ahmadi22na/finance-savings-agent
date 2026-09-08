import 'package:dio/dio.dart';

import '../core/api_client.dart';
import '../models/persona.dart';
import '../models/user.dart';

class OnboardingService {
  final ApiClient _apiClient;
  OnboardingService(this._apiClient);

  Future<List<Persona>> listPersonas() async {
    try {
      final response = await _apiClient.dio.get('/personas');
      final List data = response.data as List;
      return data
          .map((json) => Persona.fromJson(json as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }

  Future<AppUser> completeOnboarding({
    required String incomeType,
    required String personaId,
    required String goalTitle,
    required double goalTargetAmount,
    DateTime? goalDeadline,
  }) async {
    try {
      final response = await _apiClient.dio.post('/onboarding/complete', data: {
        'income_type': incomeType,
        'persona_id': personaId,
        'goal_title': goalTitle,
        'goal_target_amount': goalTargetAmount,
        if (goalDeadline != null)
          'goal_deadline': goalDeadline.toIso8601String().split('T').first,
      });
      return AppUser.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }
}
