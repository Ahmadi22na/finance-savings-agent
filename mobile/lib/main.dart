import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'theme/app_theme.dart';
import 'core/api_client.dart';

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
      home: const _StartupCheckScreen(),
    );
  }
}

/// شاشة انتقالية بسيطة: تتحقق هل عندنا توكن محفوظ (يعني المستخدم مسجّل دخول
/// من قبل) أو لأ. هاي نسخة أولية فقط للتأكد إن كل الإعداد (Dio, Secure
/// Storage, Riverpod) شغّال صح قبل ما نبني شاشات Login/Onboarding الفعلية
/// بالجزء الجاي (بيتحول وقتها لـ go_router أو Navigator حقيقي).
class _StartupCheckScreen extends StatefulWidget {
  const _StartupCheckScreen();

  @override
  State<_StartupCheckScreen> createState() => _StartupCheckScreenState();
}

class _StartupCheckScreenState extends State<_StartupCheckScreen> {
  String _status = 'جاري التحقق...';

  @override
  void initState() {
    super.initState();
    _checkSetup();
  }

  Future<void> _checkSetup() async {
    final hasToken = await ApiClient.hasToken();
    if (!mounted) return;
    setState(() {
      _status = hasToken
          ? 'في توكن محفوظ — المستخدم مسجّل دخول من قبل'
          : 'ما في توكن — لازم شاشة تسجيل دخول (الجزء الجاي)';
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Text('رشيد',
                  style: TextStyle(fontSize: 32, fontWeight: FontWeight.bold)),
              const SizedBox(height: 16),
              Text(_status, textAlign: TextAlign.center),
            ],
          ),
        ),
      ),
    );
  }
}
