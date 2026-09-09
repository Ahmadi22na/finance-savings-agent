import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'theme/app_theme.dart';
import 'core/api_client.dart';
import 'core/providers.dart';
import 'screens/auth/login_screen.dart';
import 'screens/home_placeholder_screen.dart';

void main() {
  // ProviderScope لازم يلف كل التطبيق — هو يلي بيخلي كل الـ Providers
  // (apiClientProvider, authServiceProvider...) شغالة بأي مكان بالتطبيق.
  runApp(const ProviderScope(child: RasheedApp()));
}

class RasheedApp extends StatelessWidget {
  const RasheedApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'رشيد',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      // دعم الاتجاه من اليمين لليسار — أساسي لتطبيق عربي بالكامل
      locale: const Locale('ar'),
      builder: (context, child) {
        return Directionality(
          textDirection: TextDirection.rtl,
          child: child!,
        );
      },
      home: const _SplashScreen(),
    );
  }
}

/// شاشة انتقالية عند فتح التطبيق: تتحقق هل عندنا توكن محفوظ، ولو عندنا
/// تتأكد إنه لسا صالح (بجلب بيانات المستخدم فعليًا من /users/me)، وبناءً
/// عليها توجّه المستخدم لشاشة الدخول أو للشاشة الرئيسية مباشرة.
class _SplashScreen extends ConsumerStatefulWidget {
  const _SplashScreen();

  @override
  ConsumerState<_SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends ConsumerState<_SplashScreen> {
  @override
  void initState() {
    super.initState();
    // WidgetsBinding.instance.addPostFrameCallback عشان نضمن إن الـ context
    // جاهز للـ Navigation قبل ما نستخدمه (تجنّب خطأ شائع بفلاتر).
    WidgetsBinding.instance.addPostFrameCallback((_) => _checkAuthAndNavigate());
  }

  Future<void> _checkAuthAndNavigate() async {
    final hasToken = await ApiClient.hasToken();

    if (!hasToken) {
      _goTo(const LoginScreen());
      return;
    }

    try {
      final authService = ref.read(authServiceProvider);
      final user = await authService.getCurrentUser();
      ref.read(currentUserProvider.notifier).state = user;
      _goTo(const HomePlaceholderScreen());
    } catch (_) {
      // التوكن موجود بس مو صالح (منتهي الصلاحية مثلاً) — نرجّع المستخدم لتسجيل الدخول
      await ApiClient.clearTokens();
      _goTo(const LoginScreen());
    }
  }

  void _goTo(Widget screen) {
    if (!mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => screen),
      (route) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(child: CircularProgressIndicator()),
    );
  }
}
