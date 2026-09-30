import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_sms_inbox/flutter_sms_inbox.dart';
import 'package:intl/intl.dart';
import 'package:permission_handler/permission_handler.dart';

import '../../core/api_client.dart';
import '../../core/dashboard_providers.dart';
import '../../core/providers.dart';
import '../../models/sms_import.dart';
import '../../models/transaction.dart';
import '../../widgets/income_allocation_sheet.dart';

enum _Stage { loading, permissionDenied, permanentlyDenied, nothingFound, ready, importing, failed }

/// استيراد معاملات من رسائل البنك الموجودة أصلاً بصندوق الوارد (أندرويد فقط).
///
/// الخصوصية (مقصودة بالتصميم):
/// 1. ما بنقرا الصندوق إلا بعد ما المستخدم يفتح هالشاشة ويوافق على الصلاحية.
/// 2. بنفلتر على الجهاز نفسه: ما بيطلع للسيرفر إلا رسائل فيها JOD أو "دينار".
/// 3. المستخدم بيشوف القائمة ويختار — ما بينحفظ شي بدون اختياره.
class SmsImportScreen extends ConsumerStatefulWidget {
  const SmsImportScreen({super.key});

  @override
  ConsumerState<SmsImportScreen> createState() => _SmsImportScreenState();
}

class _SmsImportScreenState extends ConsumerState<SmsImportScreen> {
  static const _scanLimit = 500; // آخر كم رسالة نقرا من الصندوق
  static const _maxDays = 90; // ما نرجع لأبعد من 3 شهور
  static const _maxUpload = 300; // نفس سقف السيرفر
  static const _financialHints = ['jod', 'دينار'];

  _Stage _stage = _Stage.loading;
  String? _errorMessage;
  List<SmsImportCandidate> _candidates = [];
  final Set<int> _selected = {};

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _stage = _Stage.loading;
      _errorMessage = null;
    });

    var status = await Permission.sms.status;
    if (!status.isGranted) {
      status = await Permission.sms.request();
    }
    if (!status.isGranted) {
      if (!mounted) return;
      setState(() {
        _stage = status.isPermanentlyDenied ? _Stage.permanentlyDenied : _Stage.permissionDenied;
      });
      return;
    }

    try {
      final inbox = await SmsQuery().querySms(kinds: [SmsQueryKind.inbox], count: _scanLimit);
      final cutoff = DateTime.now().subtract(const Duration(days: _maxDays));

      final financial = <RawSms>[];
      for (final sms in inbox) {
        final body = sms.body;
        final date = sms.date ?? sms.dateSent;
        if (body == null || date == null || date.isBefore(cutoff)) continue;
        final lower = body.toLowerCase();
        if (!_financialHints.any(lower.contains)) continue;
        financial.add(RawSms(body: body, receivedAt: date));
      }
      financial.sort((a, b) => b.receivedAt.compareTo(a.receivedAt));
      final toSend = financial.take(_maxUpload).toList();

      if (toSend.isEmpty) {
        if (mounted) setState(() => _stage = _Stage.nothingFound);
        return;
      }

      final candidates = await ref.read(transactionServiceProvider).previewSmsImport(toSend);
      if (!mounted) return;
      setState(() {
        _candidates = candidates;
        _selected
          ..clear()
          ..addAll([
            for (var i = 0; i < candidates.length; i++)
              if (!candidates[i].alreadyImported) i,
          ]);
        _stage = candidates.isEmpty ? _Stage.nothingFound : _Stage.ready;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _errorMessage = e.message;
        _stage = _Stage.failed;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _errorMessage = 'ما قدرنا نقرا الرسائل من الجهاز';
        _stage = _Stage.failed;
      });
    }
  }

  Future<void> _import() async {
    final chosen = [
      for (final index in (_selected.toList()..sort())) _candidates[index].toRawSms(),
    ];
    if (chosen.isEmpty) return;

    setState(() => _stage = _Stage.importing);
    try {
      final created = await ref.read(transactionServiceProvider).confirmSmsImport(chosen);
      ref.invalidate(recentTransactionsProvider);
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('تم استيراد ${created.length} معاملة')),
      );

      final incomes =
          created.where((t) => t.type == 'income' && t.unallocatedAmount > 0.01).toList();
      await _offerAllocation(incomes);

      if (mounted) Navigator.of(context).pop();
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _stage = _Stage.ready);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  /// القرار المتفق عليه: الدخل دايمًا نسأل المستخدم وين بدو يحطه. لو انستورد
  /// أكتر من دخل، منسأل مرة وحدة "بدك توزعهم هلأ؟" بدل ما نفاجئه بـ Sheet ورا Sheet.
  Future<void> _offerAllocation(List<Transaction> incomes) async {
    if (incomes.isEmpty || !mounted) return;

    if (incomes.length == 1) {
      await maybePromptIncomeAllocation(context, ref, incomes.first);
      return;
    }

    final go = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('وزّع الدخل المستورد'),
        content: Text('استوردت ${incomes.length} حوالة دخل. بدك توزعها على خططك هلأ، وحدة وحدة؟'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('لاحقًا'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('وزّع'),
          ),
        ],
      ),
    );
    if (go != true) return;

    for (final income in incomes) {
      if (!mounted) return;
      await maybePromptIncomeAllocation(context, ref, income);
    }
  }

  String _formatAmount(double value) {
    if (value == value.roundToDouble()) return value.toStringAsFixed(0);
    return value.toStringAsFixed(3).replaceFirst(RegExp(r'0+$'), '');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('استيراد من الرسائل')),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    switch (_stage) {
      case _Stage.loading:
      case _Stage.importing:
        return const Center(child: CircularProgressIndicator());

      case _Stage.permissionDenied:
        return _message(
          icon: Icons.sms_failed_outlined,
          text: 'بدنا صلاحية قراءة الرسائل عشان نلاقي رسائل البنك. ما بنقرا غير الرسائل المالية، وما بنحفظ شي بدون اختيارك.',
          actions: [FilledButton(onPressed: _load, child: const Text('أعطِ الصلاحية'))],
        );

      case _Stage.permanentlyDenied:
        return _message(
          icon: Icons.lock_outline,
          text: 'الصلاحية مرفوضة نهائيًا. فعّلها من إعدادات التطبيق وارجع جرّب.',
          actions: [
            FilledButton(onPressed: openAppSettings, child: const Text('افتح الإعدادات')),
            TextButton(onPressed: _load, child: const Text('جرّب من جديد')),
          ],
        );

      case _Stage.nothingFound:
        return _message(
          icon: Icons.inbox_outlined,
          text: 'ما لقينا رسائل بنكية مدعومة بآخر 3 شهور.',
          actions: [TextButton(onPressed: _load, child: const Text('حدّث'))],
        );

      case _Stage.failed:
        return _message(
          icon: Icons.error_outline,
          text: _errorMessage ?? 'صار خطأ غير متوقع',
          actions: [FilledButton(onPressed: _load, child: const Text('جرّب من جديد'))],
        );

      case _Stage.ready:
        return _buildList();
    }
  }

  Widget _message({required IconData icon, required String text, required List<Widget> actions}) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 48, color: Colors.black38),
            const SizedBox(height: 16),
            Text(text, textAlign: TextAlign.center),
            const SizedBox(height: 20),
            ...actions,
          ],
        ),
      ),
    );
  }

  Widget _buildList() {
    final dateFormat = DateFormat('yyyy/MM/dd HH:mm');

    return Column(
      children: [
        Container(
          width: double.infinity,
          color: Colors.black.withValues(alpha: 0.04),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          child: const Text(
            'قرأنا بس الرسائل المالية (فيها JOD أو دينار). اختر يلي بدك تستورده — وما بنحفظ غيره.',
            style: TextStyle(fontSize: 12, color: Colors.black54),
          ),
        ),
        Expanded(
          child: ListView.separated(
            itemCount: _candidates.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (context, index) {
              final candidate = _candidates[index];
              final isIncome = candidate.type == 'income';
              return CheckboxListTile(
                value: _selected.contains(index),
                onChanged: candidate.alreadyImported
                    ? null
                    : (checked) => setState(() {
                          if (checked == true) {
                            _selected.add(index);
                          } else {
                            _selected.remove(index);
                          }
                        }),
                title: Text(candidate.note),
                subtitle: Text(
                  candidate.alreadyImported
                      ? 'مستورد سابقًا'
                      : dateFormat.format(candidate.receivedAt.toLocal()),
                ),
                secondary: Text(
                  '${isIncome ? '+' : '-'}${_formatAmount(candidate.amount)}',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: isIncome ? Colors.green.shade700 : Colors.red.shade700,
                  ),
                ),
              );
            },
          ),
        ),
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: _selected.isEmpty ? null : _import,
                child: Text('استورد المحدد (${_selected.length})'),
              ),
            ),
          ),
        ),
      ],
    );
  }
}
