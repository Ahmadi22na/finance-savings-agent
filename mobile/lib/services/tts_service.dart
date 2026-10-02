import 'package:flutter/foundation.dart';
import 'package:flutter_tts/flutter_tts.dart';





class TtsService {
  final FlutterTts _flutterTts = FlutterTts();

  bool _initialized = false;
  bool _arabicSupported = false;

  static const _arabicLocale = 'ar-SA';





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
