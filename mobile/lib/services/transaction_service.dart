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
