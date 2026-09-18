import 'package:dio/dio.dart';

import '../core/api_client.dart';

class AgentService {
  final ApiClient _apiClient;
  AgentService(this._apiClient);

  Future<String> sendMessage(String message) async {
    try {
      final response = await _apiClient.dio.post('/agent/chat', data: {'message': message});
      return response.data['reply'] as String;
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }

  /// يرجّع نص الـ Nudge لو رشيد قرر يبادر بالحديث هلأ، أو null لو ما في داعي
  /// (رد طبيعي ومتوقع — مو خطأ). نفس منطق /agent/nudge بالـ Backend بالضبط.
  Future<String?> checkNudge() async {
    try {
      final response = await _apiClient.dio.get('/agent/nudge');
      return response.data['nudge'] as String?;
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }
}
