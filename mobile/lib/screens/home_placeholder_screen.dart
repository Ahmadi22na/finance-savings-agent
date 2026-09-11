import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/providers.dart';
import '../core/api_client.dart';
import 'auth/login_screen.dart';

/// شاشة مؤقتة بس — هدفها تأكيد إن الـ Onboarding خلص فعليًا (المستخدم عنده
/// شخصية مختارة). رح تُستبدل بالـ Dashboard الفعلي بجزء لاحق من Sprint 3
/// (Quick-log + عرض الأهداف + شات مع رشيد).
class HomePlaceholderScreen extends ConsumerWidget {
  const HomePlaceholderScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);
    final persona = user?.persona;

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
              if (persona != null)
                SizedBox(
                  height: 140,
                  child: Image.asset(persona.imageAssetPath, fit: BoxFit.contain),
                ),
              const SizedBox(height: 16),
              Text('أهلاً ${user?.name ?? ""}! 🎉',
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
              const SizedBox(height: 8),
              Text(
                persona != null
                    ? '${persona.displayName} جاهز يرافقك من هلأ'
                    : 'تسجيل الدخول نجح ✅',
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.black54),
              ),
              const SizedBox(height: 8),
              const Text(
                'الشاشة الرئيسية (Dashboard) وشات رشيد بالجزء الجاي 🚧',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.black38, fontSize: 12),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
