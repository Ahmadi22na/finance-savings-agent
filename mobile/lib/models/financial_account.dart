// الحسابات المالية اليدوية (المرحلة 1). الأرقام كلها محسوبة بالسيرفر؛ الموبايل بيعرضها فقط.
// null بالرصيد = غير معروف (مش صفر).

/// جودة الرصيد كما يرجّعها السيرفر.
const String kQualityUnknown = 'unknown';
const String kQualityManualConfirmed = 'manual_confirmed';
const String kQualityDerived = 'derived';
const String kQualityStale = 'stale';

String accountKindLabel(String kind) {
  switch (kind) {
    case 'cash':
      return 'كاش';
    case 'bank':
      return 'حساب بنكي';
    case 'wallet':
      return 'محفظة إلكترونية';
    default:
      return kind;
  }
}

String balanceQualityLabel(String quality) {
  switch (quality) {
    case kQualityManualConfirmed:
      return 'مؤكد يدوياً';
    case kQualityDerived:
      return 'محسوب من الرصيد والمعاملات';
    case kQualityStale:
      return 'قديم — يحتاج تحديث';
    case kQualityUnknown:
    default:
      return 'غير معروف';
  }
}

String snapshotSourceLabel(String source) => source == 'manual' ? 'يدوي' : source;

double? _optionalDouble(dynamic value) => value == null ? null : (value as num).toDouble();

class FinancialAccount {
  final String id;
  final String name;
  final String kind; // cash | bank | wallet
  final String currency;
  final bool isActive;
  final DateTime createdAt;
  final double? balance;
  final String balanceQuality;
  final DateTime? balanceAsOf;
  final double? lastSnapshotAmount;
  final int transactionsSinceSnapshot;
  final int ignoredBeforeSnapshot;

  FinancialAccount({
    required this.id,
    required this.name,
    required this.kind,
    required this.currency,
    required this.isActive,
    required this.createdAt,
    required this.balance,
    required this.balanceQuality,
    required this.balanceAsOf,
    required this.lastSnapshotAmount,
    required this.transactionsSinceSnapshot,
    required this.ignoredBeforeSnapshot,
  });

  factory FinancialAccount.fromJson(Map<String, dynamic> json) {
    final asOf = json['balance_as_of'];
    return FinancialAccount(
      id: json['id'] as String,
      name: json['name'] as String,
      kind: json['kind'] as String,
      currency: json['currency'] as String? ?? 'JOD',
      isActive: json['is_active'] as bool? ?? true,
      createdAt: DateTime.parse(json['created_at'] as String),
      balance: _optionalDouble(json['balance']),
      balanceQuality: json['balance_quality'] as String? ?? kQualityUnknown,
      balanceAsOf: asOf == null ? null : DateTime.parse(asOf as String),
      lastSnapshotAmount: _optionalDouble(json['last_snapshot_amount']),
      transactionsSinceSnapshot: (json['transactions_since_snapshot'] as num?)?.toInt() ?? 0,
      ignoredBeforeSnapshot: (json['ignored_before_snapshot'] as num?)?.toInt() ?? 0,
    );
  }
}

class AccountsSummary {
  final double? total;
  final int accountsTotal;
  final int accountsCounted;
  final bool hasUnknown;
  final bool hasStale;
  final bool incomplete;

  AccountsSummary({
    required this.total,
    required this.accountsTotal,
    required this.accountsCounted,
    required this.hasUnknown,
    required this.hasStale,
    required this.incomplete,
  });

  factory AccountsSummary.fromJson(Map<String, dynamic> json) {
    return AccountsSummary(
      total: _optionalDouble(json['total']),
      accountsTotal: (json['accounts_total'] as num).toInt(),
      accountsCounted: (json['accounts_counted'] as num).toInt(),
      hasUnknown: json['has_unknown'] as bool? ?? false,
      hasStale: json['has_stale'] as bool? ?? false,
      incomplete: json['incomplete'] as bool? ?? true, // لو الحقل ناقص، بنفترض الأحوط: المجموع مش كامل
    );
  }
}

class BalanceSnapshot {
  final String id;
  final double amount;
  final DateTime asOf;
  final String source;
  final DateTime createdAt;

  BalanceSnapshot({
    required this.id,
    required this.amount,
    required this.asOf,
    required this.source,
    required this.createdAt,
  });

  factory BalanceSnapshot.fromJson(Map<String, dynamic> json) {
    return BalanceSnapshot(
      id: json['id'] as String,
      amount: (json['amount'] as num).toDouble(),
      asOf: DateTime.parse(json['as_of'] as String),
      source: json['source'] as String? ?? 'manual',
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }
}
