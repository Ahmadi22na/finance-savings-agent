import 'package:flutter/material.dart';

/// ألوان كل شخصية من شخصيات رشيد — نفس القيم المخزّنة بحقل color_hex بقاعدة البيانات
/// (جدول personas). خليناها بمكان واحد بدل ما تتكرر بكل شاشة تستخدمها.
class PersonaColors {
  static const wise = Color(0xFF1B4332); // رشيد الحكيم — أخضر داكن
  static const business = Color(0xFF0B2545); // رشيد المنضبط — كحلي
  static const energetic = Color(0xFFE85D04); // رشيد الطاقة — برتقالي

  /// يحوّل مفتاح الشخصية (persona.key القادم من الـ API) للون المطابق.
  /// لو جانا مفتاح شخصية جديدة ما نعرفها بعد (تمت إضافتها بقاعدة البيانات
  /// ولسا ما حدّثنا الموبايل)، منرجع لون افتراضي بدل ما نكسر التطبيق.
  static Color fromKey(String key) {
    switch (key) {
      case 'wise':
        return wise;
      case 'business':
        return business;
      case 'energetic':
        return energetic;
      default:
        return const Color(0xFF616161); // رمادي افتراضي آمن
    }
  }
}

/// الثيم العام للتطبيق — محايد، ولون الشخصية المختارة (PersonaColors) بينحط
/// فوقه بمكانه (AppBar، أزرار رئيسية) بعد ما المستخدم يختار شخصيته بالـ Onboarding.
class AppTheme {
  static ThemeData light() {
    return ThemeData(
      useMaterial3: true,
      fontFamily: 'Cairo', // خط عربي — لازم يُضاف لاحقًا لمجلد assets/fonts لو حبينا خط مخصص
      colorScheme: ColorScheme.fromSeed(
        seedColor: PersonaColors.energetic,
        brightness: Brightness.light,
      ),
      scaffoldBackgroundColor: const Color(0xFFF7F7F5),
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
