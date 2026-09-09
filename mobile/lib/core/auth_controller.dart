import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api_client.dart';
import 'providers.dart';

/// StateNotifier بسيط يدير حالة عملية تسجيل الدخول/التسجيل (AsyncValue بيغطي
/// الحالات الثلاث: تحميل، نجاح، خطأ — بدل ما كل شاشة تدير Booleans يدويًا).
class AuthController extends StateNotifier<AsyncValue<void>> {
  final Ref _ref;
  AuthController(this._ref) : super(const AsyncValue.data(null));

  Future<void> login({required String phone, required String password}) async {
    state = const AsyncValue.loading();
    try {
      final authService = _ref.read(authServiceProvider);
      final user = await authService.login(phone: phone, password: password);
      _ref.read(currentUserProvider.notifier).state = user;
      state = const AsyncValue.data(null);
    } on ApiException catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  Future<void> register({
    required String name,
    required String phone,
    required String password,
  }) async {
    state = const AsyncValue.loading();
    try {
      final authService = _ref.read(authServiceProvider);
      final user = await authService.register(name: name, phone: phone, password: password);
      _ref.read(currentUserProvider.notifier).state = user;
      state = const AsyncValue.data(null);
    } on ApiException catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }
}

final authControllerProvider =
    StateNotifierProvider<AuthController, AsyncValue<void>>((ref) {
  return AuthController(ref);
});
