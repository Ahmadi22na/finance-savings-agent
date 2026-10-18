import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:rasheed_app/models/category.dart';
import 'package:rasheed_app/models/transaction.dart';
import 'package:rasheed_app/theme/app_theme.dart';
import 'package:rasheed_app/widgets/selectable_card.dart';
import 'package:rasheed_app/widgets/transaction_tile.dart';

/// نسبة التباين حسب WCAG 2.x. الحد الأدنى لمستوى AA للنص العادي: 4.5
double contrastRatio(Color foreground, Color background) {
  final fg = Color.alphaBlend(foreground, background).computeLuminance();
  final bg = background.computeLuminance();
  final lighter = fg > bg ? fg : bg;
  final darker = fg > bg ? bg : fg;
  return (lighter + 0.05) / (darker + 0.05);
}

const double minTextContrast = 4.5;

Transaction transaction({
  String type = 'expense',
  String source = 'manual',
  bool withCategory = true,
  String? origin,
  double? confidence,
  String note = 'غدا مع الشباب',
}) {
  return Transaction(
    id: 't1',
    amount: 12.5,
    type: type,
    source: source,
    note: note,
    occurredAt: DateTime(2026, 10, 10, 14, 30),
    category: withCategory
        ? Category(id: 'c1', name: 'مطاعم وكافيهات', icon: 'restaurant', isDefault: true, categoryType: 'expense')
        : null,
    aiSuggested: origin == 'auto',
    suggestionConfidence: confidence,
    unallocatedAmount: 0,
    categoryOrigin: origin,
    categoryConfidence: confidence,
  );
}

/// تطبيق تجريبي بنفس إعدادات التطبيق الحقيقي: عربي + RTL، وعرض شاشة هاتف (360)، مع تكبير خط اختياري.
Widget arabicApp(Widget child, {double textScale = 1.0}) {
  return MaterialApp(
    theme: AppTheme.light(),
    locale: const Locale('ar'),
    supportedLocales: const [Locale('ar')],
    localizationsDelegates: GlobalMaterialLocalizations.delegates,
    builder: (context, app) => MediaQuery(
      data: MediaQuery.of(context).copyWith(textScaler: TextScaler.linear(textScale)),
      child: app!,
    ),
    home: Scaffold(body: Center(child: SizedBox(width: 360, child: child))),
  );
}

void main() {
  group('تباين الألوان (WCAG AA ≥ 4.5:1)', () {
    test('النص الأبيض على ألوان الشخصيات (أزرار وفقاعات المحادثة)', () {
      for (final key in ['wise', 'business', 'energetic']) {
        expect(contrastRatio(Colors.white, PersonaColors.fromKey(key)), greaterThanOrEqualTo(minTextContrast),
            reason: 'شخصية $key');
      }
    });

    test('ألوان الشخصيات كنص على الأبيض وعلى خلفية التطبيق', () {
      for (final key in ['wise', 'business', 'energetic']) {
        final color = PersonaColors.fromKey(key);
        expect(contrastRatio(color, Colors.white), greaterThanOrEqualTo(minTextContrast), reason: 'شخصية $key');
        expect(contrastRatio(color, AppColors.scaffoldBackground), greaterThanOrEqualTo(minTextContrast),
            reason: 'شخصية $key');
      }
    });

    test('النص الثانوي على الأبيض وعلى خلفية التطبيق', () {
      expect(contrastRatio(AppColors.secondaryText, Colors.white), greaterThanOrEqualTo(minTextContrast));
      expect(
        contrastRatio(AppColors.secondaryText, AppColors.scaffoldBackground),
        greaterThanOrEqualTo(minTextContrast),
      );
    });

    test('مبالغ الدخل والمصروف', () {
      for (final background in [Colors.white, AppColors.scaffoldBackground]) {
        expect(contrastRatio(TransactionTile.incomeColor, background), greaterThanOrEqualTo(minTextContrast));
        expect(contrastRatio(TransactionTile.expenseColor, background), greaterThanOrEqualTo(minTextContrast));
      }
    });

    test('شارات المعاملة (المصدر، التصنيف التلقائي، بدون تصنيف)', () {
      final pairs = {
        'المصدر': [TransactionTile.neutralBadgeForeground, TransactionTile.neutralBadgeBackground],
        'تلقائي': [TransactionTile.autoBadgeForeground, TransactionTile.autoBadgeBackground],
        'بدون تصنيف': [
          TransactionTile.uncategorizedBadgeForeground,
          TransactionTile.uncategorizedBadgeBackground,
        ],
      };
      pairs.forEach((name, colors) {
        expect(contrastRatio(colors[0], colors[1]), greaterThanOrEqualTo(minTextContrast), reason: 'شارة $name');
      });
    });

    test('خلفية الـ theme هي نفسها اللي اختبرنا عليها', () {
      expect(AppTheme.light().scaffoldBackgroundColor, AppColors.scaffoldBackground);
    });
  });

  group('RTL وتكبير الخط (بدون overflow)', () {
    final variants = <String, Transaction>{
      'مصروف يدوي مصنّف': transaction(),
      'دخل من رسالة بنكية بدون تصنيف': transaction(type: 'income', source: 'sms', withCategory: false),
      'مصروف من فاتورة بتصنيف تلقائي': transaction(source: 'ocr', origin: 'auto', confidence: 0.85),
      'ملاحظة طويلة جدًا': transaction(
        withCategory: false,
        origin: null,
        note: 'وصف طويل جدًا لمعاملة غير مصنّفة عشان نتأكد إنه النص بيلف ومش بيعمل overflow',
      ),
    };

    for (final scale in [1.0, 1.5, 2.0]) {
      for (final entry in variants.entries) {
        testWidgets('${entry.key} عند تكبير الخط ${(scale * 100).round()}%', (tester) async {
          await tester.pumpWidget(arabicApp(TransactionTile(transaction: entry.value), textScale: scale));
          await tester.pump();

          expect(tester.takeException(), isNull);
        });
      }
    }

    testWidgets('الاتجاه فعلاً من اليمين لليسار', (tester) async {
      await tester.pumpWidget(arabicApp(TransactionTile(transaction: transaction())));

      final context = tester.element(find.byType(TransactionTile));
      expect(Directionality.of(context), TextDirection.rtl);
      expect(Localizations.localeOf(context).languageCode, 'ar');
    });
  });

  group('الحالات المالية ما بتعتمد على اللون وحده', () {
    testWidgets('المصروف والدخل بإشارة مكتوبة', (tester) async {
      await tester.pumpWidget(arabicApp(TransactionTile(transaction: transaction())));
      expect(find.text('-12.5'), findsOneWidget);

      await tester.pumpWidget(arabicApp(TransactionTile(transaction: transaction(type: 'income'))));
      expect(find.text('+12.5'), findsOneWidget);
    });

    testWidgets('مصدر المعاملة مكتوب بنص', (tester) async {
      for (final entry in {'manual': 'يدوي', 'ocr': 'فاتورة', 'sms': 'رسالة بنكية'}.entries) {
        await tester.pumpWidget(arabicApp(TransactionTile(transaction: transaction(source: entry.key))));
        expect(find.text(entry.value), findsOneWidget, reason: 'المصدر ${entry.key}');
      }
    });

    testWidgets('التصنيف التلقائي بنص ودرجة الثقة، وغير المصنّف بنص', (tester) async {
      await tester.pumpWidget(
        arabicApp(TransactionTile(transaction: transaction(origin: 'auto', confidence: 0.85))),
      );
      expect(find.text('تصنيف تلقائي 85%'), findsOneWidget);

      await tester.pumpWidget(arabicApp(TransactionTile(transaction: transaction(withCategory: false))));
      expect(find.text('بدون تصنيف'), findsOneWidget);
    });

    testWidgets('قارئ الشاشة بيقرا نوع المبلغ كلمة (مش بس الإشارة)', (tester) async {
      final semantics = tester.ensureSemantics();
      await tester.pumpWidget(arabicApp(TransactionTile(transaction: transaction())));
      expect(find.bySemanticsLabel(RegExp('مصروف 12.5 دينار')), findsOneWidget);

      await tester.pumpWidget(arabicApp(TransactionTile(transaction: transaction(type: 'income'))));
      expect(find.bySemanticsLabel(RegExp('دخل 12.5 دينار')), findsOneWidget);
      semantics.dispose();
    });

    testWidgets('البطاقة المختارة بتعلن إنها زر ومختارة لقارئ الشاشة', (tester) async {
      Semantics ownSemantics() => tester.widget<Semantics>(
            find.descendant(of: find.byType(SelectableCard), matching: find.byType(Semantics)).first,
          );

      await tester.pumpWidget(arabicApp(
        SelectableCard(isSelected: true, onTap: () {}, child: const Text('رشيد الحكيم')),
      ));
      expect(ownSemantics().properties.selected, isTrue);
      expect(ownSemantics().properties.button, isTrue);

      await tester.pumpWidget(arabicApp(
        SelectableCard(isSelected: false, onTap: () {}, child: const Text('رشيد الحكيم')),
      ));
      expect(ownSemantics().properties.selected, isFalse);
    });
  });
}
