import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_client.dart';
import '../../core/providers.dart';
import '../auth/login_screen.dart';

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
          Icon(icon, size: 20, color: Colors.black54),
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
