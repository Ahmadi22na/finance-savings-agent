import 'package:dio/dio.dart';

import '../core/api_client.dart';
import '../models/category.dart';

class CategoryService {
  final ApiClient _apiClient;
  CategoryService(this._apiClient);

  Future<List<Category>> listCategories() async {
    try {
      final response = await _apiClient.dio.get('/categories');
      final List data = response.data as List;
      return data.map((json) => Category.fromJson(json as Map<String, dynamic>)).toList();
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }
}
