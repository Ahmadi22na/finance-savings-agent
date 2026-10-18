import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_client.dart';
import '../../core/onboarding_providers.dart';
import '../../core/providers.dart';
import '../../models/persona.dart';
import '../../theme/app_theme.dart';
import '../../widgets/selectable_card.dart';
import '../auth/login_screen.dart';

/// وسوم التقييم الجاهزة (المفتاح = القيمة اللي بتنبعت للسيرفر). بدون نص حر لحماية الخصوصية.
const Map<String, String> _feedbackTagLabels = {
  'helpful': 'مفيد',
  'friendly': 'أسلوبه حلو',
  'motivating': 'بيحمّسني',
  'too_long': 'طويل زيادة',
  'too_pushy': 'ضاغط زيادة',
  'confusing': 'مش واضح',
};

/// شاشة "حسابي والخصوصية": ملخص بسيط لكيف بنتعامل مع بياناتك، وتسجيل الخروج، وحذف الحساب نهائيًا.
class AccountScreen extends ConsumerWidget {
  const AccountScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('حسابي والخصوصية')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          ListTile(
            leading: const CircleAvatar(child: Icon(Icons.person_outline)),
            title: Text(user?.name ?? ''),
            subtitle: Text(user?.phone ?? ''),
          ),
          const Divider(),
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 8),
            child: Text('خصوصيتك', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          ),
          const _PrivacyPoint(
            icon: Icons.storage_outlined,
            text: 'بنخزّن بياناتك المالية (الأهداف والمعاملات والمحادثات) على سيرفرنا لتشغيل التطبيق فقط.',
          ),
          const _PrivacyPoint(
            icon: Icons.smart_toy_outlined,
            text: 'لما تحكي مع رشيد أو تمسح فاتورة، النص أو الصورة بتنبعت لخدمة Google Gemini عشان ترد عليك.',
          ),
          const _PrivacyPoint(
            icon: Icons.sms_outlined,
            text: 'الرسائل البنكية: بنقراها فقط بموافقتك، وبنفلتر الرسائل المالية على جهازك، وما بنخزّن نص الرسالة.',
          ),
          const _PrivacyPoint(
            icon: Icons.delete_outline,
            text: 'بتقدر تحذف حسابك وكل بياناتك بأي وقت من هون.',
          ),
          const Divider(height: 32),
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 8),
            child: Text('رشيد', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          ),
          ListTile(
            leading: const Icon(Icons.face_outlined),
            title: const Text('غيّر شخصية رشيد'),
            subtitle: Text(user?.persona?.displayName ?? ''),
            onTap: () => _openSheet(context, const _PersonaSwitcherSheet()),
          ),
          ListTile(
            leading: const Icon(Icons.star_outline),
            title: const Text('قيّم رشيد'),
            subtitle: const Text('تقييم سريع بيساعدنا نحسّن الشخصيات'),
            onTap: () => _openSheet(context, const _PersonaFeedbackSheet()),
          ),
          const Divider(height: 32),
          ListTile(
            leading: const Icon(Icons.logout),
            title: const Text('تسجيل الخروج'),
            onTap: () => _logout(context, ref),
          ),
          ListTile(
            leading: Icon(Icons.delete_forever_outlined, color: Colors.red.shade700),
            title: Text('حذف حسابي وكل بياناتي', style: TextStyle(color: Colors.red.shade700)),
            subtitle: const Text('نهائي ولا يمكن التراجع عنه'),
            onTap: () => _startDelete(context, ref),
          ),
        ],
      ),
    );
  }

  Future<void> _openSheet(BuildContext context, Widget sheet) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => sheet,
    );
  }

  Future<void> _logout(BuildContext context, WidgetRef ref) async {
    await ref.read(authServiceProvider).logout();
    ref.read(currentUserProvider.notifier).state = null;
    if (!context.mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const LoginScreen()),
      (route) => false,
    );
  }

  Future<void> _startDelete(BuildContext context, WidgetRef ref) async {
    final deleted = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => const _DeleteAccountDialog(),
    );
    if (deleted != true || !context.mounted) return;

    ref.read(currentUserProvider.notifier).state = null;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const LoginScreen()),
      (route) => false,
    );
  }
}

class _PrivacyPoint extends StatelessWidget {
  final IconData icon;
  final String text;

  const _PrivacyPoint({required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 20, color: AppColors.secondaryText),
          const SizedBox(width: 12),
          Expanded(child: Text(text, style: const TextStyle(fontSize: 13, height: 1.5))),
        ],
      ),
    );
  }
}

class _DeleteAccountDialog extends ConsumerStatefulWidget {
  const _DeleteAccountDialog();

  @override
  ConsumerState<_DeleteAccountDialog> createState() => _DeleteAccountDialogState();
}

class _DeleteAccountDialogState extends ConsumerState<_DeleteAccountDialog> {
  final _passwordController = TextEditingController();
  bool _isDeleting = false;
  String? _error;

  @override
  void dispose() {
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _delete() async {
    final password = _passwordController.text;
    if (password.isEmpty) return;

    setState(() {
      _isDeleting = true;
      _error = null;
    });

    try {
      await ref.read(authServiceProvider).deleteAccount(password: password);
      if (mounted) Navigator.of(context).pop(true);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _isDeleting = false;
        _error = e.message;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _isDeleting = false;
        _error = 'صار خطأ غير متوقع، جرب كمان شوي';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final canDelete = !_isDeleting && _passwordController.text.isNotEmpty;

    return AlertDialog(
      title: const Text('حذف الحساب نهائيًا؟'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'رح نحذف حسابك وكل بياناتك: الأهداف والمعاملات وتوزيعات الدخل ومحادثاتك مع رشيد والاقتراحات. '
              'ما في طريقة للتراجع.',
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _passwordController,
              obscureText: true,
              enabled: !_isDeleting,
              onChanged: (_) => setState(() {}),
              decoration: InputDecoration(
                labelText: 'كلمة المرور للتأكيد',
                errorText: _error,
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: _isDeleting ? null : () => Navigator.of(context).pop(false),
          child: const Text('إلغاء'),
        ),
        FilledButton(
          style: FilledButton.styleFrom(backgroundColor: Colors.red.shade700),
          onPressed: canDelete ? _delete : null,
          child: _isDeleting
              ? const SizedBox(
                  height: 18,
                  width: 18,
                  child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                )
              : const Text('احذف حسابي'),
        ),
      ],
    );
  }
}

/// ورقة تبديل الشخصية: التبديل بيغيّر أسلوب رشيد فقط، الأرقام والأهداف ما بتتغيّر.
class _PersonaSwitcherSheet extends ConsumerStatefulWidget {
  const _PersonaSwitcherSheet();

  @override
  ConsumerState<_PersonaSwitcherSheet> createState() => _PersonaSwitcherSheetState();
}

class _PersonaSwitcherSheetState extends ConsumerState<_PersonaSwitcherSheet> {
  bool _isSaving = false;

  Future<void> _switchTo(Persona persona) async {
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _isSaving = true);
    try {
      final updated = await ref.read(onboardingServiceProvider).changePersona(persona.id);
      ref.read(currentUserProvider.notifier).state = updated;
      if (!mounted) return;
      Navigator.of(context).pop();
      messenger.showSnackBar(SnackBar(content: Text('صار ${persona.displayName} معك ✅')));
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _isSaving = false);
      messenger.showSnackBar(SnackBar(content: Text(e.message)));
    } catch (_) {
      if (!mounted) return;
      setState(() => _isSaving = false);
      messenger.showSnackBar(const SnackBar(content: Text('ما قدرنا نبدّل الشخصية، جرب كمان شوي')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final personasAsync = ref.watch(personasListProvider);
    final currentId = ref.watch(currentUserProvider)?.persona?.id;

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('اختار شخصية رشيد', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 4),
            const Text(
              'جرّب الشخصيات براحتك. بتتغيّر طريقة حديث رشيد فقط، وأرقامك وأهدافك بتضل زي ما هي.',
              style: TextStyle(color: AppColors.secondaryText, fontSize: 13, height: 1.4),
            ),
            const SizedBox(height: 16),
            personasAsync.when(
              loading: () => const Center(
                child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator()),
              ),
              error: (_, __) => const Text('ما قدرنا نحمّل الشخصيات، جرب كمان شوي'),
              data: (personas) => Flexible(
                child: ListView.separated(
                  shrinkWrap: true,
                  itemCount: personas.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 10),
                  itemBuilder: (context, index) {
                    final persona = personas[index];
                    final isCurrent = persona.id == currentId;
                    final color = PersonaColors.fromKey(persona.key);
                    return SelectableCard(
                      isSelected: isCurrent,
                      selectedColor: color,
                      onTap: () {
                        if (!_isSaving && !isCurrent) _switchTo(persona);
                      },
                      child: Row(
                        children: [
                          SizedBox(
                            height: 64,
                            width: 50,
                            child: Image.asset(persona.imageAssetPath, fit: BoxFit.contain, excludeFromSemantics: true),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  persona.displayName,
                                  style: TextStyle(fontWeight: FontWeight.bold, color: color),
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  persona.tagline,
                                  style: const TextStyle(color: AppColors.secondaryText, fontSize: 12),
                                ),
                              ],
                            ),
                          ),
                          if (isCurrent)
                            Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(Icons.check_circle, color: color, size: 18),
                                const SizedBox(width: 4),
                                Text('الحالية', style: TextStyle(color: color, fontSize: 12)),
                              ],
                            ),
                        ],
                      ),
                    );
                  },
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// ورقة تقييم مختصر للشخصية الحالية: نجوم 1-5 + وسوم جاهزة (بدون نص حر).
class _PersonaFeedbackSheet extends ConsumerStatefulWidget {
  const _PersonaFeedbackSheet();

  @override
  ConsumerState<_PersonaFeedbackSheet> createState() => _PersonaFeedbackSheetState();
}

class _PersonaFeedbackSheetState extends ConsumerState<_PersonaFeedbackSheet> {
  int _rating = 0;
  final Set<String> _tags = {};
  bool _isSaving = false;

  @override
  void initState() {
    super.initState();
    _loadPreviousFeedback();
  }

  /// لو المستخدم قيّم هالشخصية قبل، منعبّي التقييم السابق عشان يقدر يعدّله.
  Future<void> _loadPreviousFeedback() async {
    final persona = ref.read(currentUserProvider)?.persona;
    if (persona == null) return;
    try {
      final all = await ref.read(onboardingServiceProvider).myPersonaFeedback();
      final previous = all.where((item) => item['persona_id'] == persona.id).toList();
      if (previous.isEmpty || !mounted) return;
      setState(() {
        _rating = previous.first['rating'] as int;
        _tags
          ..clear()
          ..addAll((previous.first['tags'] as List).map((tag) => tag as String));
      });
    } catch (_) {
      // التقييم السابق اختياري؛ لو فشل التحميل منكمل بنموذج فاضي
    }
  }

  Future<void> _submit(Persona persona) async {
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _isSaving = true);
    try {
      await ref.read(onboardingServiceProvider).submitPersonaFeedback(
            personaId: persona.id,
            rating: _rating,
            tags: _tags.toList(),
          );
      if (!mounted) return;
      Navigator.of(context).pop();
      messenger.showSnackBar(const SnackBar(content: Text('شكرًا لتقييمك 🙏')));
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _isSaving = false);
      messenger.showSnackBar(SnackBar(content: Text(e.message)));
    } catch (_) {
      if (!mounted) return;
      setState(() => _isSaving = false);
      messenger.showSnackBar(const SnackBar(content: Text('ما قدرنا نرسل التقييم، جرب كمان شوي')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final persona = ref.watch(currentUserProvider)?.persona;

    if (persona == null) {
      return const SafeArea(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text('اختار شخصية لرشيد أول عشان تقدر تقيّمها'),
        ),
      );
    }

    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('كيف كان ${persona.displayName}؟',
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 4),
            const Text('تقييمك بيساعدنا نعرف أي شخصية بتفيد الناس أكتر.',
                style: TextStyle(color: AppColors.secondaryText, fontSize: 13)),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                for (int star = 1; star <= 5; star++)
                  IconButton(
                    tooltip: '$star من 5',
                    iconSize: 34,
                    onPressed: _isSaving ? null : () => setState(() => _rating = star),
                    icon: Icon(
                      star <= _rating ? Icons.star : Icons.star_border,
                      color: Colors.amber.shade700,
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final entry in _feedbackTagLabels.entries)
                  FilterChip(
                    label: Text(entry.value),
                    selected: _tags.contains(entry.key),
                    onSelected: _isSaving
                        ? null
                        : (selected) => setState(() {
                              if (selected) {
                                _tags.add(entry.key);
                              } else {
                                _tags.remove(entry.key);
                              }
                            }),
                  ),
              ],
            ),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: (_rating == 0 || _isSaving) ? null : () => _submit(persona),
                child: _isSaving
                    ? const SizedBox(
                        height: 18,
                        width: 18,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : const Text('أرسل التقييم'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

