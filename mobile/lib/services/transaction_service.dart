import 'dart:io';

import 'package:dio/dio.dart';

import '../core/api_client.dart';
import '../models/transaction.dart';
import '../models/receipt_scan_result.dart';
import '../models/sms_parse_result.dart';
import '../models/sms_import.dart';

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

  /// يحلل نص رسالة بنكية ملصوقة يدويًا (بدون أي صلاحية قراءة رسائل) ويرجّع
  /// مسودة — ما بتنشئ أي معاملة، المستخدم لازم يراجعها ويحفظها بنفسه.
  Future<SmsParseResult> parseSms(String text) async {
    try {
      final response = await _apiClient.dio.post('/transactions/parse-sms', data: {
        'text': text,
      });
      return SmsParseResult.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }

  /// يحلل رسائل مقروءة من صندوق الوارد ويرجّع معاملات مقترحة (ما بيحفظ شي).
  Future<List<SmsImportCandidate>> previewSmsImport(List<RawSms> messages) async {
    try {
      final response = await _apiClient.dio.post('/transactions/sms-import/preview', data: {
        'messages': messages.map((m) => m.toJson()).toList(),
      });
      final items = response.data['candidates'] as List;
      return items
          .map((json) => SmsImportCandidate.fromJson(json as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }

  /// ينشئ معاملات فعلية من الرسائل يلي اختارها المستخدم. السيرفر بيعيد تحليل
  /// النص بنفسه، وبيتجاهل الرسائل يلي انستوردت قبل (منع التكرار بالبصمة).
  Future<List<Transaction>> confirmSmsImport(List<RawSms> messages) async {
    try {
      final response = await _apiClient.dio.post('/transactions/sms-import/confirm', data: {
        'messages': messages.map((m) => m.toJson()).toList(),
      });
      final items = response.data as List;
      return items
          .map((json) => Transaction.fromJson(json as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }
}
