import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// عنوان الـ Backend. لما تشغّل التطبيق على محاكي أندرويد (Emulator)، لازم
/// تستخدم 10.0.2.2 بدل localhost (هيك بيوصّلك للجهاز المضيف). لو جهاز حقيقي
/// على نفس الشبكة، استخدم IP الجهاز الفعلي (مثلاً 192.168.x.x).
const String kApiBaseUrl = 'http://10.0.2.2:8000/api/v1';

const _secureStorage = FlutterSecureStorage();
const _accessTokenKey = 'access_token';
const _refreshTokenKey = 'refresh_token';

/// طبقة اتصال واحدة مشتركة لكل التطبيق — نظير BaseAIProvider بالـ Backend
/// بفلسفتها: كل الشاشات بتتعامل مع هاي الطبقة، ما حدا بيسوي HTTP request
/// مباشرة من الواجهة.
class ApiClient {
  late final Dio dio;

  ApiClient() {
    dio = Dio(BaseOptions(
      baseUrl: kApiBaseUrl,
      connectTimeout: const Duration(seconds: 15),
      receiveTimeout: const Duration(seconds: 15),
    ));

    // هذا الـ Interceptor بيضيف "Authorization: Bearer <token>" تلقائيًا
    // لأي طلب — بدل ما نكتبها يدويًا بكل استدعاء API بكل شاشة.
    dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await _secureStorage.read(key: _accessTokenKey);
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        handler.next(options);
      },
    ));
  }

  static Future<void> saveTokens({
    required String accessToken,
    required String refreshToken,
  }) async {
    await _secureStorage.write(key: _accessTokenKey, value: accessToken);
    await _secureStorage.write(key: _refreshTokenKey, value: refreshToken);
  }

  static Future<void> clearTokens() async {
    await _secureStorage.delete(key: _accessTokenKey);
    await _secureStorage.delete(key: _refreshTokenKey);
  }

  static Future<bool> hasToken() async {
    final token = await _secureStorage.read(key: _accessTokenKey);
    return token != null;
  }
}

/// استثناء موحّد لأخطاء الـ API — يحوّل أي خطأ Dio لرسالة عربية مفهومة
/// بدل ما كل شاشة تتعامل مع تفاصيل Dio التقنية بنفسها.
class ApiException implements Exception {
  final String message;
  final int? statusCode;

  ApiException(this.message, {this.statusCode});

  factory ApiException.fromDioError(DioException e) {
    final response = e.response;
    if (response != null && response.data is Map) {
      final detail = response.data['detail'];
      if (detail is String) {
        return ApiException(detail, statusCode: response.statusCode);
      }
    }
    if (e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.receiveTimeout) {
      return ApiException('الاتصال بالسيرفر أخذ وقت أطول من اللازم، تأكد من اتصالك');
    }
    if (e.type == DioExceptionType.connectionError) {
      return ApiException('ما قدرنا نوصل للسيرفر — تأكد إنه شغّال');
    }
    return ApiException('صار خطأ غير متوقع، جرب كمان شوي');
  }
}
