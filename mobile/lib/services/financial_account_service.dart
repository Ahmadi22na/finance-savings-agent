import 'package:dio/dio.dart';

import '../core/api_client.dart';
import '../models/financial_account.dart';

/// رسائل واضحة بدل التفاصيل التقنية: 400/409 رسائلها من السيرفر عربية وموجّهة للمستخدم، والباقي بنحوّله هون.
ApiException _toException(DioException e) {
  final status = e.response?.statusCode;
  final data = e.response?.data;
  final detail = (data is Map && data['detail'] is String) ? data['detail'] as String : null;

  switch (status) {
    case 400:
    case 409:
      return ApiException(detail ?? 'ما قدرنا ننفّذ الطلب، راجع البيانات وجرب كمان مرة', statusCode: status);
    case 401:
      return ApiException('انتهت جلستك، سجّل دخولك من جديد', statusCode: status);
    case 404:
      return ApiException('هذا الحساب غير موجود، ممكن يكون انحذف', statusCode: status);
    case 422:
      return ApiException('تأكد من القيم المدخلة (الاسم مش فاضي، والمبلغ حتى 3 خانات عشرية)', statusCode: status);
  }
  if (status != null && status >= 500) {
    return ApiException('صار خطأ بالسيرفر، جرب كمان شوي', statusCode: status);
  }
  final generic = ApiException.fromDioError(e);
  return ApiException(generic.message, statusCode: status);
}

class FinancialAccountService {
  final ApiClient _apiClient;
  FinancialAccountService(this._apiClient);

  Future<List<FinancialAccount>> listAccounts({bool includeArchived = false}) async {
    try {
      final response = await _apiClient.dio.get('/accounts', queryParameters: {'include_archived': includeArchived});
      final List data = response.data as List;
      return data.map((json) => FinancialAccount.fromJson(json as Map<String, dynamic>)).toList();
    } on DioException catch (e) {
      throw _toException(e);
    }
  }

  Future<AccountsSummary> getSummary() async {
    try {
      final response = await _apiClient.dio.get('/accounts/summary');
      return AccountsSummary.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw _toException(e);
    }
  }

  Future<FinancialAccount> createAccount({
    required String name,
    required String kind,
    double? openingBalance,
  }) async {
    try {
      final response = await _apiClient.dio.post('/accounts', data: {
        'name': name,
        'kind': kind,
        if (openingBalance != null) 'opening_balance': openingBalance,
      });
      return FinancialAccount.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw _toException(e);
    }
  }

  /// بنرسل بس الحقول المتغيّرة (السيرفر بيرفض جسمًا فاضيًا).
  Future<FinancialAccount> updateAccount(String accountId, {String? name, String? kind, bool? isActive}) async {
    try {
      final response = await _apiClient.dio.patch('/accounts/$accountId', data: {
        if (name != null) 'name': name,
        if (kind != null) 'kind': kind,
        if (isActive != null) 'is_active': isActive,
      });
      return FinancialAccount.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw _toException(e);
    }
  }

  /// 409 = الحساب عليه معاملات أو لقطات رصيد (السيرفر هو اللي بيقرر، مش الواجهة).
  Future<void> deleteAccount(String accountId) async {
    try {
      await _apiClient.dio.delete('/accounts/$accountId');
    } on DioException catch (e) {
      throw _toException(e);
    }
  }

  /// لقطة رصيد جديدة. asOf اختياري (الافتراضي بالسيرفر: الآن)؛ السيرفر هو اللي بيحسب أثرها على الرصيد.
  Future<FinancialAccount> addBalance(String accountId, {required double amount, DateTime? asOf}) async {
    try {
      final response = await _apiClient.dio.post('/accounts/$accountId/balance', data: {
        'amount': amount,
        if (asOf != null) 'as_of': asOf.toUtc().toIso8601String(),
      });
      return FinancialAccount.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw _toException(e);
    }
  }

  Future<List<BalanceSnapshot>> listSnapshots(String accountId) async {
    try {
      final response = await _apiClient.dio.get('/accounts/$accountId/snapshots');
      final List data = response.data as List;
      return data.map((json) => BalanceSnapshot.fromJson(json as Map<String, dynamic>)).toList();
    } on DioException catch (e) {
      throw _toException(e);
    }
  }
}
