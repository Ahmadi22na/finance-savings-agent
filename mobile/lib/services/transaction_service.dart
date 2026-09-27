import 'dart:io';

import 'package:dio/dio.dart';

import '../core/api_client.dart';
import '../models/transaction.dart';
import '../models/receipt_scan_result.dart';

class TransactionService {
  final ApiClient _apiClient;
  TransactionService(this._apiClient);

  Future<List<Transaction>> listTransactions({int limit = 50}) async {
    try {
      final response = await _apiClient.dio.get('/transactions', queryParameters: {
        'limit': limit,
      });
      final List data = response.data as List;
      return data.map((json) => Transaction.fromJson(json as Map<String, dynamic>)).toList();
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }

  /// التسجيل السريع — يدعم المسارين سوا (نفس منطق الـ Backend بالضبط):
  /// - وصل categoryId؟ → حفظ فوري بدون أي معالجة إضافية (مسار الأيقونات)
  /// - ما وصل categoryId بس وصل note؟ → محرك التصنيف الذكي يحاول يخمّن
  Future<Transaction> quickLog({
    required double amount,
    required String type, // 'income' أو 'expense'
    String? categoryId,
    String? note,
  }) async {
    try {
      final response = await _apiClient.dio.post('/transactions/quick-log', data: {
        'amount': amount,
        'type': type,
        if (categoryId != null) 'category_id': categoryId,
        if (note != null && note.trim().isNotEmpty) 'note': note.trim(),
      });
      return Transaction.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }

  /// توزيع معاملة دخل واحدة (كل أو جزء منها) على خطة أو أكتر — دايمًا
  /// بقرار صريح من المستخدم، رشيد ما بيوزع شي من عنده. بيرجّع المعاملة
  /// المحدّثة (unallocated_amount ممكن يضل أكبر من صفر لو الهدف اكتفى
  /// بأقل من المبلغ المطلوب — الباقي يضل بانتظار توزيع تاني).
  Future<Transaction> allocateIncome({
    required String transactionId,
    required List<Map<String, dynamic>> allocations,
  }) async {
    try {
      final response = await _apiClient.dio.post('/transactions/$transactionId/allocate', data: {
        'allocations': allocations,
      });
      return Transaction.fromJson(response.data['transaction'] as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }

  /// يرفع صورة فاتورة ويرجّع مسودة (مبلغ + تصنيف مقترح + ملاحظة) — ما بتنشئ
  /// أي معاملة، المستخدم لازم يراجعها ويحفظها بنفسه عبر quickLog العادي.
  Future<ReceiptScanResult> scanReceipt(File imageFile) async {
    try {
      final formData = FormData.fromMap({
        'file': await MultipartFile.fromFile(
          imageFile.path,
          filename: imageFile.path.split(Platform.pathSeparator).last,
        ),
      });
      final response = await _apiClient.dio.post(
        '/transactions/scan-receipt',
        data: formData,
        // قراءة صورة عبر Gemini Vision ممكن تاخد وقت أطول من نداء نصي عادي
        options: Options(receiveTimeout: const Duration(seconds: 30)),
      );
      return ReceiptScanResult.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }
}
