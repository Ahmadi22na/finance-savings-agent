import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api_client.dart';
import '../services/auth_service.dart';
import '../services/onboarding_service.dart';
import '../services/goal_service.dart';
import '../services/transaction_service.dart';
import '../models/user.dart';

/// Provider واحد لـ ApiClient — كل الخدمات بتاخذه من هون، ما حدا بيسوي
/// Dio() جديد بنفسه. نظير get_db() بالـ Backend (مصدر وحيد للاتصال).
final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());

final authServiceProvider = Provider<AuthService>((ref) {
  return AuthService(ref.watch(apiClientProvider));
});

final onboardingServiceProvider = Provider<OnboardingService>((ref) {
  return OnboardingService(ref.watch(apiClientProvider));
});

final goalServiceProvider = Provider<GoalService>((ref) {
  return GoalService(ref.watch(apiClientProvider));
});

final transactionServiceProvider = Provider<TransactionService>((ref) {
  return TransactionService(ref.watch(apiClientProvider));
});

/// حالة المستخدم الحالي عبر كل التطبيق — أي شاشة تقدر "تسمع" لأي تغيير هون
/// (مثلاً بعد تسجيل الدخول أو إكمال الـ Onboarding) وتحدّث نفسها تلقائيًا.
final currentUserProvider = StateProvider<AppUser?>((ref) => null);
