import 'package:dio/dio.dart';

import '../core/api_client.dart';
import '../models/goal.dart';

class GoalService {
  final ApiClient _apiClient;
  GoalService(this._apiClient);

  Future<List<Goal>> listGoals() async {
    try {
      final response = await _apiClient.dio.get('/goals');
      final List data = response.data as List;
      return data.map((json) => Goal.fromJson(json as Map<String, dynamic>)).toList();
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }

  Future<Goal> createGoal({
    required String title,
    required double targetAmount,
    DateTime? deadline,
  }) async {
    try {
      final response = await _apiClient.dio.post('/goals', data: {
        'title': title,
        'target_amount': targetAmount,
        if (deadline != null) 'deadline': deadline.toIso8601String().split('T').first,
      });
      return Goal.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }

  Future<Goal> contributeToGoal({required String goalId, required double amount}) async {
    try {
      final response =
          await _apiClient.dio.post('/goals/$goalId/contribute', data: {'amount': amount});
      return Goal.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }

  Future<void> deleteGoal(String goalId) async {
    try {
      await _apiClient.dio.delete('/goals/$goalId');
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }
}
