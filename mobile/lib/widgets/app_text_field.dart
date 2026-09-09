import 'package:flutter/material.dart';

/// حقل نص موحّد الشكل — نستخدمه بكل شاشات المصادقة (وبعدين Onboarding)
/// بدل ما نكرر نفس الـ decoration بكل شاشة.
class AppTextField extends StatelessWidget {
  final TextEditingController controller;
  final String label;
  final bool obscureText;
  final TextInputType keyboardType;
  final String? Function(String?)? validator;

  const AppTextField({
    super.key,
    required this.controller,
    required this.label,
    this.obscureText = false,
    this.keyboardType = TextInputType.text,
    this.validator,
  });

  @override
  Widget build(BuildContext context) {
    return TextFormField(
      controller: controller,
      obscureText: obscureText,
      keyboardType: keyboardType,
      textAlign: TextAlign.right,
      decoration: InputDecoration(labelText: label),
      validator: validator,
    );
  }
}
