import 'package:dio/dio.dart';

import '../core/api_client.dart';
import '../models/agent_action.dart';

class AgentService {
  final ApiClient _apiClient;
  AgentService(this._apiClient);

  Future<String> sendMessage(String message) async {
    try {
      final response = await _apiClient.dio.post(
        '/agent/chat',
        data: {'message': message},





        options: Options(receiveTimeout: const Duration(seconds: 45)),
      );
      return response.data['reply'] as String;
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }



  Future<String?> checkNudge() async {
    try {
      final response = await _apiClient.dio.get('/agent/nudge');
      return response.data['nudge'] as String?;
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }


  Future<List<AgentAction>> listPendingActions() async {
    try {
      final response = await _apiClient.dio.get('/agent/actions');
      final List data = response.data as List;
      return data.map((json) => AgentAction.fromJson(json as Map<String, dynamic>)).toList();
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }



  Future<List<AgentAction>> checkForNewActions() async {
    try {
      final response = await _apiClient.dio.post('/agent/actions/check');
      final List data = response.data as List;
      return data.map((json) => AgentAction.fromJson(json as Map<String, dynamic>)).toList();
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }

  Future<AgentAction> confirmAction(String actionId) async {
    try {
      final response = await _apiClient.dio.post('/agent/actions/$actionId/confirm');
      return AgentAction.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }

  Future<AgentAction> rejectAction(String actionId) async {
    try {
      final response = await _apiClient.dio.post('/agent/actions/$actionId/reject');
      return AgentAction.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }
}
