import 'package:dio/dio.dart';

import '../core/api_client.dart';
import '../models/user.dart';

class AuthService {
  final ApiClient _apiClient;
  AuthService(this._apiClient);

  Future<AppUser> register({
    required String name,
    required String phone,
    required String password,
  }) async {
    try {
      final response = await _apiClient.dio.post('/auth/register', data: {
        'name': name,
        'phone': phone,
        'password': password,
      });
      return _handleTokenResponse(response.data);
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }

  Future<AppUser> login({
    required String phone,
    required String password,
  }) async {
    try {
      final response = await _apiClient.dio.post('/auth/login', data: {
        'phone': phone,
        'password': password,
      });
      return _handleTokenResponse(response.data);
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }

  Future<AppUser> getCurrentUser() async {
    try {
      final response = await _apiClient.dio.get('/users/me');
      return AppUser.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }

  Future<void> logout() async {
    await ApiClient.clearTokens();
  }

  Future<AppUser> _handleTokenResponse(Map<String, dynamic> data) async {
    await ApiClient.saveTokens(
      accessToken: data['access_token'] as String,
      refreshToken: data['refresh_token'] as String,
    );
    return AppUser.fromJson(data['user'] as Map<String, dynamic>);
  }
}
