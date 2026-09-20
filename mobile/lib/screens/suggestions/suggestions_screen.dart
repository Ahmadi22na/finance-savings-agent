import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../core/agent_action_providers.dart';
import '../../core/dashboard_providers.dart';
import '../../core/api_client.dart';
import '../../models/agent_action.dart';
import '../../theme/app_theme.dart';

class SuggestionsScreen extends ConsumerStatefulWidget {
  const SuggestionsScreen({super.key});

  @override
  ConsumerState<SuggestionsScreen> createState() => _SuggestionsScreenState();
}

class _SuggestionsScreenState extends ConsumerState<SuggestionsScreen> {
  bool _isChecking = true;
  final _respondingIds = <String>{}; // نمنع ضغط مزدوج على نفس البطاقة وهي قيد التنفيذ

  @override
  void initState() {
    super.initState();
    // أول ما تفتح الشاشة، منفحص فعليًا إذا في اقتراحات جديدة تستاهل (نفس فكرة
    // فحص الـ Nudge عند فتح الشات) — هون بس بيصير أي استدعاء AI فعلي بهالميزة.
    WidgetsBinding.instance.addPostFrameCallback((_) => _checkForNew());
  }

  Future<void> _checkForNew() async {
    try {
      final agentService = ref.read(agentServiceProvider);
      await agentService.checkForNewActions();
    } catch (_) {
      // فشل الفحص مش شي حرج — الشاشة بتعرض أي اقتراحات موجودة أصلاً بهدوء
    } finally {
      if (mounted) {
        setState(() => _isChecking = false);
        ref.invalidate(pendingActionsProvider);
      }
    }
  }

  Future<void> _respond(AgentAction action, {required bool confirm}) async {
    setState(() => _respondingIds.add(action.id));
    try {
      final agentService = ref.read(agentServiceProvider);
      if (confirm) {
        await agentService.confirmAction(action.id);
        // التطبيق الفعلي ممكن يغيّر أهداف أو معاملات — نحدّث الـ Dashboard تلقائيًا
        ref.invalidate(goalsListProvider);
        ref.invalidate(recentTransactionsProvider);
      } else {
        await agentService.rejectAction(action.id);
      }
      ref.invalidate(pendingActionsProvider);
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _respondingIds.remove(action.id));
    }
  }

  @override
  Widget build(BuildContext context) {
    final actionsAsync = ref.watch(pendingActionsProvider);
    final user = ref.watch(currentUserProvider);
    final accentColor =
        user?.persona != null ? PersonaColors.fromKey(user!.persona!.key) : PersonaColors.energetic;

    return Scaffold(
      appBar: AppBar(title: const Text('اقتراحات رشيد')),
      body: RefreshIndicator(
        onRefresh: () async {
          setState(() => _isChecking = true);
          await _checkForNew();
        },
        child: actionsAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) => ListView(
            children: [
              const SizedBox(height: 80),
              Center(child: Text('ما قدرنا نجيب الاقتراحات: $error')),
            ],
          ),
          data: (actions) {
            if (actions.isEmpty) {
              return ListView(
                children: [
                  SizedBox(height: MediaQuery.of(context).size.height * 0.25),
                  Icon(
                    _isChecking ? Icons.hourglass_empty : Icons.check_circle_outline,
                    size: 56,
                    color: Colors.black26,
                  ),
                  const SizedBox(height: 16),
                  Text(
                    _isChecking ? 'رشيد عم يراجع وضعك...' : 'ولا اقتراح جديد هلأ — كل شي تمام 👍',
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Colors.black54),
                  ),
                ],
              );
            }
            return ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: actions.length,
              itemBuilder: (context, index) {
                final action = actions[index];
                final isResponding = _respondingIds.contains(action.id);
                return _SuggestionCard(
                  action: action,
                  accentColor: accentColor,
                  isResponding: isResponding,
                  onConfirm: () => _respond(action, confirm: true),
                  onReject: () => _respond(action, confirm: false),
                );
              },
            );
          },
        ),
      ),
    );
  }
}

class _SuggestionCard extends StatelessWidget {
  final AgentAction action;
  final Color accentColor;
  final bool isResponding;
  final VoidCallback onConfirm;
  final VoidCallback onReject;

  const _SuggestionCard({
    required this.action,
    required this.accentColor,
    required this.isResponding,
    required this.onConfirm,
    required this.onReject,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(_iconForActionType(action.actionType), color: accentColor, size: 20),
              const SizedBox(width: 8),
              Expanded(child: _buildTitle(context)),
            ],
          ),
          const SizedBox(height: 10),
          if (action.reasoning != null && action.reasoning!.isNotEmpty)
            Text(action.reasoning!, style: const TextStyle(color: Colors.black87, fontSize: 13)),
          const SizedBox(height: 14),
          if (isResponding)
            const Center(
              child: Padding(
                padding: EdgeInsets.symmetric(vertical: 8),
                child: SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2)),
              ),
            )
          else
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(onPressed: onReject, child: const Text('رفض')),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: ElevatedButton(
                    onPressed: onConfirm,
                    style: ElevatedButton.styleFrom(backgroundColor: accentColor),
                    child: const Text('موافق'),
                  ),
                ),
              ],
            ),
        ],
      ),
    );
  }

  Widget _buildTitle(BuildContext context) {
    if (action.actionType == 'suggest_category_correction') {
      final note = action.payload['transaction_note'] as String? ?? '';
      final amount = action.payload['transaction_amount'];
      final categoryName = action.payload['new_category_name'] as String? ?? '';
      return RichText(
        text: TextSpan(
          style: DefaultTextStyle.of(context).style.copyWith(fontSize: 14),
          children: [
            const TextSpan(text: 'تصنيف معاملة: ', style: TextStyle(fontWeight: FontWeight.bold)),
            TextSpan(text: '"$note" ($amount) ← '),
            TextSpan(text: categoryName, style: const TextStyle(fontWeight: FontWeight.bold)),
          ],
        ),
      );
    }

    if (action.actionType == 'suggest_goal_contribution') {
      final goalTitle = action.payload['goal_title'] as String? ?? '';
      final amount = action.payload['amount'];
      return RichText(
        text: TextSpan(
          style: DefaultTextStyle.of(context).style.copyWith(fontSize: 14),
          children: [
            const TextSpan(text: 'إضافة ', style: TextStyle(fontWeight: FontWeight.bold)),
            TextSpan(text: '$amount دينار '),
            const TextSpan(text: 'لهدف '),
            TextSpan(text: goalTitle, style: const TextStyle(fontWeight: FontWeight.bold)),
          ],
        ),
      );
    }

    return const Text('اقتراح من رشيد');
  }

  IconData _iconForActionType(String type) {
    switch (type) {
      case 'suggest_category_correction':
        return Icons.label_important_outline;
      case 'suggest_goal_contribution':
        return Icons.savings_outlined;
      default:
        return Icons.lightbulb_outline;
    }
  }
}
