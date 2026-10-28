import 'package:intl/intl.dart';

/// عرض وإدخال مبالغ الحسابات المالية فقط. ما في أي حساب أرصدة هون: كل الأرقام بتجي جاهزة من السيرفر.

/// نتيجة تحليل مبلغ مكتوب: إما [value] أو رسالة [error] جاهزة للعرض.
class MoneyParse {
  final double? value;
  final String? error;

  const MoneyParse.ok(this.value) : error = null;
  const MoneyParse.error(this.error) : value = null;
}

/// أقصى عدد منازل للجزء الصحيح: يطابق NUMERIC(14,3) بالسيرفر (14 منزلة بالمجموع، منها 3 عشرية).
const int kMaxIntegerDigits = 11;

/// يحلّل مبلغًا موقّعًا (السالب والصفر مسموحين) بحد أقصى 3 خانات عشرية.
/// بيقبل الأرقام العربية والفاصلة العربية/الإنجليزية كفاصلة عشرية.
/// "1,000" بنرفضه عن قصد: ممكن تكون ألف أو 1.000، وما بنخمّن بالأموال.
MoneyParse parseSignedMoney(String raw) {
  var text = raw.trim();
  if (text.isEmpty) return const MoneyParse.error('اكتب المبلغ');

  const arabicDigits = '٠١٢٣٤٥٦٧٨٩';
  for (var i = 0; i < arabicDigits.length; i++) {
    text = text.replaceAll(arabicDigits[i], '$i');
  }
  text = text.replaceAll('\u2212', '-').replaceAll('\u200E', '').replaceAll('\u200F', '');

  if (RegExp(r'^-?\d{1,3}[,،]\d{3}$').hasMatch(text)) {
    return const MoneyParse.error('اكتب الرقم بدون فاصلة آلاف، مثال: 1000 أو 1000.5');
  }

  text = text.replaceAll('٫', '.').replaceAll('،', '.').replaceAll(',', '.');
  final match = RegExp(r'^(-)?(\d+)(?:\.(\d{1,3}))?$').firstMatch(text);
  if (match == null) {
    return const MoneyParse.error('اكتب رقمًا صحيحًا (حتى 3 خانات عشرية)، مثال: 120.5 أو -15');
  }

  final integerPart = match.group(2)!;
  final significantDigits = integerPart.replaceFirst(RegExp(r'^0+(?=\d)'), '').length;
  if (significantDigits > kMaxIntegerDigits) {
    return const MoneyParse.error('الرقم كبير كثير، تأكد من المبلغ');
  }

  final decimals = match.group(3);
  final value = double.parse(decimals == null ? integerPart : '$integerPart.$decimals');
  if (value == 0) return const MoneyParse.ok(0.0); // "-0" بتصير 0 عادي
  return MoneyParse.ok(match.group(1) != null ? -value : value);
}

/// مبلغ للعرض: بدون أصفار زايدة (100 / 12.5 / 0.3 / -3.125). بنحط علامة اتجاه (LRM) عشان الإشارة تبقى جنب الرقم بالـ RTL.
String formatMoney(double value) {
  final fixed = value.abs().toStringAsFixed(3);
  final trimmed = fixed.replaceFirst(RegExp(r'\.?0+$'), '');
  final sign = value < 0 && trimmed != '0' ? '-' : '';
  return '\u200E$sign$trimmed';
}

/// "قبل 5 دقيقة" وما شابه. للتواريخ الأقدم من 30 يوم بنعرض التاريخ نفسه.
String relativeArabic(DateTime when, {DateTime? now}) {
  final difference = (now ?? DateTime.now()).difference(when);
  if (difference.isNegative || difference.inMinutes < 1) return 'الآن';
  if (difference.inMinutes < 60) return 'قبل ${difference.inMinutes} دقيقة';
  if (difference.inHours < 24) return 'قبل ${difference.inHours} ساعة';
  if (difference.inDays < 30) return 'قبل ${difference.inDays} يوم';
  return DateFormat('d/M/yyyy').format(when.toLocal());
}
