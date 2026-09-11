import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/auth_controller.dart';
import '../../core/api_client.dart';
import '../../core/providers.dart';
import '../../widgets/app_text_field.dart';
import 'register_screen.dart';
import '../onboarding/onboarding_flow_screen.dart';
import '../home_placeholder_screen.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _phoneController = TextEditingController();
  final _passwordController = TextEditingController();

  @override
  void dispose() {
    _phoneController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;

    await ref.read(authControllerProvider.notifier).login(
          phone: _phoneController.text.trim(),
          password: _passwordController.text,
        );

    final state = ref.read(authControllerProvider);
    if (!mounted) return;

    state.whenOrNull(
      data: (_) {
        final user = ref.read(currentUserProvider);
        final nextScreen = (user?.hasCompletedOnboarding ?? false)
            ? const HomePlaceholderScreen()
            : const OnboardingFlowScreen();
        // نجح الدخول — نستبدل الشاشة كاملة (المستخدم ما يقدر يرجع لشاشة الدخول بالـ Back)
        Navigator.of(context).pushAndRemoveUntil(
          MaterialPageRoute(builder: (_) => nextScreen),
          (route) => false,
        );
      },
      error: (error, _) {
        final message = error is ApiException ? error.message : 'صار خطأ غير متوقع';
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authControllerProvider);
    final isLoading = authState.isLoading;

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const SizedBox(height: 48),
                const Text('رشيد',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 36, fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                const Text('وفّر مصاريك ووصل لأهدافك',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 15, color: Colors.black54)),
                const SizedBox(height: 48),
                AppTextField(
                  controller: _phoneController,
                  label: 'رقم الهاتف',
                  keyboardType: TextInputType.phone,
                  validator: (value) {
                    if (value == null || value.trim().length < 8) {
                      return 'رقم الهاتف غير صحيح';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 16),
                AppTextField(
                  controller: _passwordController,
                  label: 'كلمة المرور',
                  obscureText: true,
                  validator: (value) {
                    if (value == null || value.length < 8) {
                      return 'كلمة المرور 8 أحرف على الأقل';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 24),
                ElevatedButton(
                  onPressed: isLoading ? null : _submit,
                  child: isLoading
                      ? const SizedBox(
                          height: 20, width: 20,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        )
                      : const Text('تسجيل الدخول'),
                ),
                const SizedBox(height: 16),
                TextButton(
                  onPressed: isLoading
                      ? null
                      : () => Navigator.of(context).push(
                            MaterialPageRoute(builder: (_) => const RegisterScreen()),
                          ),
                  child: const Text('ما عندك حساب؟ سجّل من هون'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
