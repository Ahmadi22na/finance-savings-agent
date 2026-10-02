import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api_client.dart';
import '../services/auth_service.dart';
import '../services/onboarding_service.dart';
import '../services/goal_service.dart';
import '../services/transaction_service.dart';
import '../services/category_service.dart';
import '../services/agent_service.dart';
import '../services/tts_service.dart';
import '../models/user.dart';



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

final categoryServiceProvider = Provider<CategoryService>((ref) {
  return CategoryService(ref.watch(apiClientProvider));
});

final agentServiceProvider = Provider<AgentService>((ref) {
  return AgentService(ref.watch(apiClientProvider));
});



final ttsServiceProvider = Provider<TtsService>((ref) => TtsService());



final currentUserProvider = StateProvider<AppUser?>((ref) => null);
