import 'package:flutter/foundation.dart';
import 'package:flutter_tts/flutter_tts.dart';

/// يتحكم بصوت رشيد وينطق ردوده. نفرّق بين الشخصيات الثلاث بالسرعة ونبرة
/// الصوت (pitch/rate) بدل الاعتماد على أصوات منفصلة مثبتة بالجهاز — عدد
/// الأصوات العربية المتوفرة يختلف من جهاز لآخر (بعض الأجهزة فيها صوت
/// عربي واحد بس، أو ولا وحدة)، بينما pitch/rate شغالة على أي محرك TTS.
class TtsService {
  final FlutterTts _flutterTts = FlutterTts();

  bool _initialized = false;
  bool _arabicSupported = false;

  static const _arabicLocale = 'ar-SA';

  // (نبرة، سرعة) لكل شخصية — القيم مبنية على الشخصية المكتوبة أصلًا
  // بالـ System Prompts: الحكيم هادئ وبطيء، المنضبط ثابت، الطاقة حماسي وسريع.
  // ملاحظة Dart: لازم أقواس مجعّدة {} عشان حقول الـ Record تصير قابلة
  // للوصول بالاسم (.pitch) — بدونها بتصير حقول مرقّمة بس ($1, $2).
  static const Map<String, ({double pitch, double rate})> _voiceProfiles = {
    'wise': (pitch: 0.85, rate: 0.42),
    'business': (pitch: 1.0, rate: 0.50),
    'energetic': (pitch: 1.25, rate: 0.58),
  };

  Future<void> _ensureInitialized() async {
    if (_initialized) return;
    try {
      final available = await _flutterTts.isLanguageAvailable(_arabicLocale);
      _arabicSupported = available == true || available == 1;
      if (_arabicSupported) {
        await _flutterTts.setLanguage(_arabicLocale);
      }
    } catch (_) {
      _arabicSupported = false;
    }
    _initialized = true;
  }

  /// يرجّع false لو جهاز المستخدم ما فيه صوت عربي مثبت أصلًا — الشاشة
  /// بتعرض رسالة واضحة بهالحالة بدل ما تحاول تنطق بصوت إنجليزي غريب.
  Future<bool> speak(
    String text, {
    required String personaKey,
    VoidCallback? onDone,
  }) async {
    await _ensureInitialized();
    if (!_arabicSupported) return false;

    final profile = _voiceProfiles[personaKey] ?? _voiceProfiles['business']!;
    await _flutterTts.setPitch(profile.pitch);
    await _flutterTts.setSpeechRate(profile.rate);

    _flutterTts.setCompletionHandler(() => onDone?.call());
    _flutterTts.setCancelHandler(() => onDone?.call());
    _flutterTts.setErrorHandler((_) => onDone?.call());

    await _flutterTts.speak(text);
    return true;
  }

  Future<void> stop() => _flutterTts.stop();
}
