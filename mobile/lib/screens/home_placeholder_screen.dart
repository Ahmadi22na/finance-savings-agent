import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/providers.dart';
import '../core/api_client.dart';
import 'auth/login_screen.dart';

/// شاشة مؤقتة بس — هدفها تأكيد إن تسجيل الدخول/التسجيل نجح فعليًا ووصلنا
/// بيانات المستخدم من الـ Backend. رح تُستبدل بالجزء الجاي بمنطق حقيقي:
/// لو has_completed_onboarding == false → شاشات اختيار الشخصية وأول هدف،
/// لو true → الـ Dashboard الفعلي.
class HomePlaceholderScreen extends ConsumerWidget {
  const HomePlaceholderScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);

    return Scaffold(
      appBar: AppBar(
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () async {
              await ApiClient.clearTokens();
              ref.read(currentUserProvider.notifier).state = null;
              if (context.mounted) {
                Navigator.of(context).pushAndRemoveUntil(
                  MaterialPageRoute(builder: (_) => const LoginScreen()),
                  (route) => false,
                );
              }
            },
          ),
        ],
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.check_circle, color: Colors.green, size: 64),
              const SizedBox(height: 16),
              Text('أهلاً ${user?.name ?? ""}! تسجيل الدخول نجح ✅',
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              Text(
                user?.hasCompletedOnboarding == true
                    ? 'خلّصت الـ Onboarding من قبل'
                    : 'لسا ما خلّصت الـ Onboarding — شاشاته بالجزء الجاي',
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.black54),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
