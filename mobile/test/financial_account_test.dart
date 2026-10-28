import 'package:flutter_test/flutter_test.dart';

import 'package:rasheed_app/core/account_format.dart';
import 'package:rasheed_app/models/financial_account.dart';

void main() {
  group('parseSignedMoney', () {
    double? ok(String raw) {
      final result = parseSignedMoney(raw);
      expect(result.error, isNull, reason: 'متوقع قبول "$raw"');
      return result.value;
    }

    String? error(String raw) {
      final result = parseSignedMoney(raw);
      expect(result.value, isNull, reason: 'متوقع رفض "$raw"');
      return result.error;
    }

    test('بيقبل الموجب والسالب والصفر', () {
      expect(ok('12.5'), 12.5);
      expect(ok('-12.5'), -12.5);
      expect(ok('0'), 0.0);
      expect(ok('٠'), 0.0);
      expect(ok('100'), 100.0);
    });

    test('السالب صفر بيصير صفر عادي (مش -0.0)', () {
      final value = ok('-0')!;
      expect(value, 0.0);
      expect(value.isNegative, isFalse);
    });

    test('الأرقام والفاصلة والإشارة العربية', () {
      expect(ok('٣٫٥'), 3.5);
      expect(ok('١٢،٥'), 12.5);
      expect(ok('1,5'), 1.5);
      expect(ok('\u2212٧'), -7.0); // علامة ناقص يونيكود
      expect(ok('  7  '), 7.0);
    });

    test('بيقبل لحد 3 خانات عشرية ويرفض الأكتر', () {
      expect(ok('1.234'), 1.234);
      expect(ok('0.001'), 0.001);
      expect(error('1.2345'), isNotNull);
      expect(error('0.0005'), isNotNull);
    });

    test('بيرفض الفاصلة الملتبسة (ألف أو 1.000) بدل ما يخمّن', () {
      expect(error('1,000'), contains('بدون فاصلة آلاف'));
      expect(error('12,345'), isNotNull);
      expect(ok('1.000'), 1.0); // بالنقطة واضحة: 3 خانات عشرية
    });

    test('بيرفض الصيغ الغلط والفاضي', () {
      for (final raw in ['', '   ', 'abc', '-', '--5', '5-', '+5', '1.', '.5', '1e5', '1 000', '1.2.3']) {
        expect(error(raw), isNotNull, reason: raw);
      }
    });

    test('حد المنازل: 11 منزلة صحيحة بالأكثر (يطابق NUMERIC(14,3))', () {
      expect(ok('12345678901.123'), 12345678901.123);
      expect(error('123456789012'), isNotNull);
      expect(ok('0000000000001'), 1.0); // الأصفار البادئة ما بتنحسب
    });
  });

  group('formatMoney', () {
    test('بدون أصفار زايدة، والإشارة مع علامة اتجاه', () {
      expect(formatMoney(100), '\u200E100');
      expect(formatMoney(12.5), '\u200E12.5');
      expect(formatMoney(0.1 + 0.2), '\u200E0.3');
      expect(formatMoney(-3.125), '\u200E-3.125');
      expect(formatMoney(100.05), '\u200E100.05');
    });

    test('الصفر والقيم الأصغر من فلس ما بتطلع -0', () {
      expect(formatMoney(0), '\u200E0');
      expect(formatMoney(-0.0), '\u200E0');
      expect(formatMoney(-0.0004), '\u200E0');
    });
  });

  group('relativeArabic', () {
    final now = DateTime(2026, 10, 25, 12, 0);

    test('الآن ودقايق وساعات وأيام', () {
      expect(relativeArabic(now.subtract(const Duration(seconds: 20)), now: now), 'الآن');
      expect(relativeArabic(now.add(const Duration(minutes: 3)), now: now), 'الآن'); // فرق ساعة جهاز بسيط
      expect(relativeArabic(now.subtract(const Duration(minutes: 5)), now: now), 'قبل 5 دقيقة');
      expect(relativeArabic(now.subtract(const Duration(hours: 3)), now: now), 'قبل 3 ساعة');
      expect(relativeArabic(now.subtract(const Duration(days: 12)), now: now), 'قبل 12 يوم');
    });

    test('الأقدم من 30 يوم بيعرض التاريخ', () {
      expect(relativeArabic(DateTime(2026, 8, 1, 9), now: now), '1/8/2026');
    });
  });

  group('الموديلات (عقد الـ API)', () {
    Map<String, dynamic> account({Object? balance = 12, String quality = 'derived', Object? asOf}) => {
          'id': 'a1',
          'name': 'الكاش',
          'kind': 'cash',
          'currency': 'JOD',
          'is_active': true,
          'created_at': '2026-10-20T10:00:00Z',
          'balance': balance,
          'balance_quality': quality,
          'balance_as_of': asOf,
          'last_snapshot_amount': balance,
          'transactions_since_snapshot': 2,
          'ignored_before_snapshot': 1,
        };

    test('الرصيد المجهول بيضل null (مش صفر)', () {
      final parsed = FinancialAccount.fromJson(account(balance: null, quality: 'unknown'));
      expect(parsed.balance, isNull);
      expect(parsed.lastSnapshotAmount, isNull);
      expect(parsed.balanceAsOf, isNull);
      expect(parsed.balanceQuality, kQualityUnknown);
    });

    test('الأرقام الصحيحة من JSON بتتحول double، والتاريخ بيتقرا', () {
      final parsed = FinancialAccount.fromJson(account(balance: 100, asOf: '2026-10-21T08:30:00Z'));
      expect(parsed.balance, 100.0);
      expect(parsed.balanceAsOf, DateTime.utc(2026, 10, 21, 8, 30));
      expect(parsed.transactionsSinceSnapshot, 2);
      expect(parsed.ignoredBeforeSnapshot, 1);
    });

    test('الملخص: total null بيضل null، وincomplete الناقص بيعتبر غير كامل', () {
      final summary = AccountsSummary.fromJson({
        'total': null, 'accounts_total': 2, 'accounts_counted': 0, 'has_unknown': true, 'has_stale': false,
        'incomplete': true,
      });
      expect(summary.total, isNull);
      expect(summary.incomplete, isTrue);

      final missingFlag = AccountsSummary.fromJson({'total': 5, 'accounts_total': 1, 'accounts_counted': 1});
      expect(missingFlag.incomplete, isTrue); // الحقل غايب → الأحوط
    });

    test('اللقطة', () {
      final snapshot = BalanceSnapshot.fromJson({
        'id': 's1', 'amount': -15, 'as_of': '2026-10-20T09:00:00Z', 'source': 'manual',
        'created_at': '2026-10-20T09:01:00Z',
      });
      expect(snapshot.amount, -15.0);
      expect(snapshotSourceLabel(snapshot.source), 'يدوي');
      expect(snapshotSourceLabel('provider'), 'provider');
    });
  });

  group('التسميات', () {
    test('جودة الرصيد حسب التسميات المعتمدة', () {
      expect(balanceQualityLabel('unknown'), 'غير معروف');
      expect(balanceQualityLabel('manual_confirmed'), 'مؤكد يدوياً');
      expect(balanceQualityLabel('derived'), 'محسوب من الرصيد والمعاملات');
      expect(balanceQualityLabel('stale'), 'قديم — يحتاج تحديث');
      expect(balanceQualityLabel('شي جديد'), 'غير معروف'); // قيمة غير معروفة: الأحوط
    });

    test('أنواع الحسابات', () {
      expect(accountKindLabel('cash'), 'كاش');
      expect(accountKindLabel('bank'), 'حساب بنكي');
      expect(accountKindLabel('wallet'), 'محفظة إلكترونية');
    });
  });
}
