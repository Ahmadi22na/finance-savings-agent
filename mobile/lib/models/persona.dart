/// يطابق app/schemas/persona.py -> PersonaOut بالـ Backend بالضبط.
/// أي تغيير بشكل الرد هناك لازم ينعكس هون يدويًا (ما في type-sharing تلقائي
/// بين Python وDart، فهاي نقطة لازم تنتبهلها لو عدّلت الـ Backend لاحقًا).
class Persona {
  final String id;
  final String key;
  final String displayName;
  final String tagline;
  final String colorHex;

  Persona({
    required this.id,
    required this.key,
    required this.displayName,
    required this.tagline,
    required this.colorHex,
  });

  factory Persona.fromJson(Map<String, dynamic> json) {
    return Persona(
      id: json['id'] as String,
      key: json['key'] as String,
      displayName: json['display_name'] as String,
      tagline: json['tagline'] as String,
      colorHex: json['color_hex'] as String,
    );
  }

  /// مسار صورة الـ Asset المحلية المطابقة لهاي الشخصية (اسم الملف = key بالضبط).
  String get imageAssetPath => 'assets/images/personas/$key.png';
}
