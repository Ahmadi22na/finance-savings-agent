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




  Future<Transaction> quickLog({
    required double amount,
    required String type,
    String? categoryId,
    String? note,
    String source = 'manual',
    String? accountId,
  }) async {
    try {
      final response = await _apiClient.dio.post('/transactions/quick-log', data: {
        'amount': amount,
        'type': type,
        if (categoryId != null) 'category_id': categoryId,
        if (note != null && note.trim().isNotEmpty) 'note': note.trim(),
        if (source != 'manual') 'source': source,
        if (accountId != null) 'account_id': accountId,
      });
      return Transaction.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }

  /// ربط معاملة بحساب مالي نشط أو نقلها لحساب آخر، أو فك الربط (accountId = null). ما بيتغيّر شي ثاني بالمعاملة.
  /// السيرفر بيرفض الحساب المؤرشف أو الغريب، وبيرفض تغيير حساب طرف تحويل.
  Future<Transaction> moveToAccount(String transactionId, String? accountId) async {
    try {
      final response = await _apiClient.dio.patch('/transactions/$transactionId', data: {
        'account_id': accountId,
      });
      return Transaction.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }

  /// تعديل تصنيف معاملة (categoryId = null بيزيل التصنيف). بعد التعديل بيصير التصنيف "من المستخدم".
  Future<Transaction> updateCategory(String transactionId, String? categoryId) async {
    try {
      final response = await _apiClient.dio.patch('/transactions/$transactionId', data: {
        'category_id': categoryId,
      });
      return Transaction.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }





  /// تعديل مبلغ/ملاحظة/وقت معاملة. بنرسل بس الحقول المتغيّرة؛ clearNote=true بيمسح الملاحظة.
  Future<Transaction> updateTransaction(
    String transactionId, {
    double? amount,
    String? note,
    bool clearNote = false,
    DateTime? occurredAt,
  }) async {
    try {
      final response = await _apiClient.dio.patch('/transactions/$transactionId', data: {
        if (amount != null) 'amount': amount,
        if (clearNote) 'note': null else if (note != null) 'note': note.trim(),
        if (occurredAt != null) 'occurred_at': occurredAt.toUtc().toIso8601String(),
      });
      return Transaction.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }

  /// حذف معاملة. لو كانت دخلاً موزَّعًا، السيرفر بيعكس التوزيعات (مبالغ الأهداف بتنقص).
  Future<void> deleteTransaction(String transactionId) async {
    try {
      await _apiClient.dio.delete('/transactions/$transactionId');
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }

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

        options: Options(receiveTimeout: const Duration(seconds: 30)),
      );
      return ReceiptScanResult.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDioError(e);
    }
  }



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
