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
    String? goalTitle, // الهدف الأول اختياري: العنوان والمبلغ مع بعض أو ولا واحد منهم
    double? goalTargetAmount,
    DateTime? goalDeadline,
  }) async {
    try {
      final response = await _apiClient.dio.post('/onboarding/complete', data: {
        'income_type': incomeType,
        'persona_id': personaId,
        if (goalTitle != null && goalTargetAmount != null) ...{
          'goal_title': goalTitle,
          'goal_target_amount': goalTargetAmount,
          if (goalDeadline != null)
            'goal_deadline': goalDeadline.toIso8601String().split('T').first,
        },
      });
      return AppUser.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }

  /// تبديل شخصية رشيد بأي وقت (للتجربة). بيغيّر أسلوب الحديث فقط، والأرقام المالية ما بتتأثر.
  Future<AppUser> changePersona(String personaId) async {
    try {
      final response = await _apiClient.dio.patch('/users/me/persona', data: {
        'persona_id': personaId,
      });
      return AppUser.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }

  /// تقييم مختصر (1-5 + وسوم جاهزة). إعادة الإرسال بتحدّث التقييم السابق لنفس الشخصية.
  Future<void> submitPersonaFeedback({
    required String personaId,
    required int rating,
    required List<String> tags,
  }) async {
    try {
      await _apiClient.dio.put('/users/me/persona-feedback', data: {
        'persona_id': personaId,
        'rating': rating,
        'tags': tags,
      });
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }

  /// تقييماتي السابقة (عشان نعبّي النموذج لو المستخدم بده يعدّل تقييمه).
  Future<List<Map<String, dynamic>>> myPersonaFeedback() async {
    try {
      final response = await _apiClient.dio.get('/users/me/persona-feedback');
      final List data = response.data as List;
      return data.map((item) => item as Map<String, dynamic>).toList();
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }
}
