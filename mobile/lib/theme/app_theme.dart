import 'package:flutter/material.dart';



class PersonaColors {
  static const wise = Color(0xFF1B4332);
  static const business = Color(0xFF0B2545);
  // كان E85D04: تباينه مع النص الأبيض (أزرار وفقاعات المحادثة) أقل من 4.5:1 فبيفشل WCAG AA للنصوص الصغيرة.
  // C2410C: نفس العائلة البرتقالية، وتباينه مع الأبيض ~5.2:1. (قرار تصميم: ارجع للقديم لو بدك، بس بيفشل الاختبار)
  static const energetic = Color(0xFFC2410C);




  static Color fromKey(String key) {
    switch (key) {
      case 'wise':
        return wise;
      case 'business':
        return business;
      case 'energetic':
        return energetic;
      default:
        return const Color(0xFF616161);
    }
  }
}



/// ألوان ثابتة بتحقق تباين WCAG AA (≥ 4.5:1) على الأبيض وعلى خلفية التطبيق.
/// كانت النصوص الثانوية بـ Colors.black54 (تباينها 4.3:1 فقط على خلفية التطبيق F7F7F5).
class AppColors {
  static const Color secondaryText = Color(0xFF616161);
  static const Color scaffoldBackground = Color(0xFFF7F7F5);
}

class AppTheme {
  static ThemeData light() {
    return ThemeData(
      useMaterial3: true,
      fontFamily: 'Cairo',
      colorScheme: ColorScheme.fromSeed(
        seedColor: PersonaColors.energetic,
        brightness: Brightness.light,
      ),
      scaffoldBackgroundColor: AppColors.scaffoldBackground,
      appBarTheme: const AppBarTheme(
        elevation: 0,
        centerTitle: true,
        backgroundColor: Colors.transparent,
        foregroundColor: Colors.black87,
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          padding: const EdgeInsets.symmetric(vertical: 16),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide.none,
        ),
      ),
    );
  }
}
