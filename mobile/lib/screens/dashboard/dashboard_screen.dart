import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../core/dashboard_providers.dart';
import '../../core/agent_action_providers.dart';
import '../../core/api_client.dart';
import '../../models/goal.dart';
import '../../theme/app_theme.dart';
import '../../widgets/goal_progress_card.dart';
import '../../widgets/transaction_tile.dart';
import '../auth/login_screen.dart';
import '../quick_log/quick_log_screen.dart';
import '../chat/chat_screen.dart';
import '../suggestions/suggestions_screen.dart';
import '../goal_path/goal_path_screen.dart';
import '../add_goal/add_goal_screen.dart';
import '../sms_import/sms_import_screen.dart';

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);
    final transactionsAsync = ref.watch(recentTransactionsProvider);
    final pendingActionsAsync = ref.watch(pendingActionsProvider);
    final pendingCount = pendingActionsAsync.value?.length ?? 0;
    final accentColor =
        user?.persona != null ? PersonaColors.fromKey(user!.persona!.key) : PersonaColors.energetic;

    return Scaffold(
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (user?.persona != null)
              Padding(
                padding: const EdgeInsets.only(left: 8),
                child: SizedBox(
                  height: 32,
                  child: Image.asset(user!.persona!.imageAssetPath, fit: BoxFit.contain),
                ),
              ),
            Text('أهلًا ${user?.name ?? ""}'),
          ],
        ),
        actions: [
          IconButton(
            icon: Badge(
              label: Text('$pendingCount'),
              isLabelVisible: pendingCount > 0,
              child: const Icon(Icons.lightbulb_outline),
            ),
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const SuggestionsScreen()),
              ).then((_) => ref.invalidate(pendingActionsProvider));
            },
          ),
          IconButton(
            icon: const Icon(Icons.chat_bubble_outline),
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const ChatScreen()),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () async {
              await ApiClient.clearTokens();
              ref.read(currentUserProvider.notifier).state = null;
              if (context.mounted) {
                Navigator.of(context).pushAndRemoveUntil(
                  MaterialPageRoute(builder: (_) => const LoginScreen()),
                  (route) => false,
                );
              }
            },
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: accentColor,
        onPressed: () {
          Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => const QuickLogScreen()),
          );
        },
        icon: const Icon(Icons.add),
        label: const Text('تسجيل سريع'),
      ),
      body: RefreshIndicator(
        onRefresh: () async {


          ref.invalidate(goalsListProvider);
          ref.invalidate(recentTransactionsProvider);
        },
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Row(
              children: [
                const Expanded(
                  child: Text('أهدافك', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                ),
                IconButton(
                  icon: const Icon(Icons.add_circle_outline),
                  tooltip: 'هدف جديد',
                  onPressed: () => Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => const AddGoalScreen()),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            const Text(
              'اسحب من ⠿ لترتيب أولوياتك',
              style: TextStyle(fontSize: 12, color: Colors.black45),
            ),
            const SizedBox(height: 12),
            _GoalsSection(accentColor: accentColor),
            const SizedBox(height: 28),
            const Text('آخر المعاملات', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const SmsImportScreen()),
              ),
              icon: const Icon(Icons.sms_outlined, size: 18),
              label: const Text('استورد من رسائل البنك'),
            ),
            const SizedBox(height: 8),
            transactionsAsync.when(
              loading: () => const Center(
                child: Padding(
                  padding: EdgeInsets.all(24),
                  child: CircularProgressIndicator(),
                ),
              ),
              error: (error, _) => Text('ما قدرنا نجيب معاملاتك: $error'),
              data: (transactions) {
                if (transactions.isEmpty) {
                  return const Padding(
                    padding: EdgeInsets.symmetric(vertical: 16),
                    child: Text('ما في معاملات مسجّلة بعد', style: TextStyle(color: Colors.black54)),
                  );
                }
                return Column(
                  children: transactions
                      .map((t) => TransactionTile(transaction: t))
                      .toList(),
                );
              },
            ),
            const SizedBox(height: 80),
          ],
        ),
      ),
    );
  }
}



///



class _GoalsSection extends ConsumerStatefulWidget {
  final Color accentColor;
  const _GoalsSection({required this.accentColor});

  @override
  ConsumerState<_GoalsSection> createState() => _GoalsSectionState();
}

class _GoalsSectionState extends ConsumerState<_GoalsSection> {
  List<Goal>? _localActiveOrder;






  bool _matchesServer(List<Goal> local, List<Goal> server) {
    if (local.length != server.length) return false;
    for (var i = 0; i < local.length; i++) {
      final a = local[i];
      final b = server[i];
      if (a.id != b.id ||
          a.currentAmount != b.currentAmount ||
          a.targetAmount != b.targetAmount ||
          a.priority != b.priority ||
          a.isRecurring != b.isRecurring) {
        return false;
      }
    }
    return true;
  }

  @override
  Widget build(BuildContext context) {
    final goalsAsync = ref.watch(goalsListProvider);

    return goalsAsync.when(
      loading: () => const Center(
        child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator()),
      ),
      error: (error, _) => Text('ما قدرنا نجيب أهدافك: $error'),
      data: (goals) {
        if (goals.isEmpty) {
          return const Padding(
            padding: EdgeInsets.symmetric(vertical: 16),
            child: Text('ما عندك أهداف بعد', style: TextStyle(color: Colors.black54)),
          );
        }

        final serverActive = goals.where((g) => g.status == 'active').toList();
        final others = goals.where((g) => g.status != 'active').toList();





        if (_localActiveOrder == null || !_matchesServer(_localActiveOrder!, serverActive)) {
          _localActiveOrder = serverActive;
        }
        final activeGoals = _localActiveOrder!;

        return Column(
          children: [
            if (activeGoals.isNotEmpty)
              ReorderableListView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                buildDefaultDragHandles: false,
                itemCount: activeGoals.length,


                onReorderItem: (oldIndex, newIndex) {
                  setState(() {
                    final moved = activeGoals.removeAt(oldIndex);
                    activeGoals.insert(newIndex, moved);
                  });



                  ref
                      .read(goalServiceProvider)
                      .reorderGoals(activeGoals.map((g) => g.id).toList())
                      .catchError((_) => <Goal>[])
                      .whenComplete(() => ref.invalidate(goalsListProvider));
                },
                itemBuilder: (context, index) {
                  final goal = activeGoals[index];
                  return Padding(
                    key: ValueKey(goal.id),
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Row(
                      children: [
                        ReorderableDragStartListener(
                          index: index,
                          child: const Padding(
                            padding: EdgeInsets.only(left: 6),
                            child: Icon(Icons.drag_indicator, color: Colors.black38),
                          ),
                        ),
                        Expanded(
                          child: GestureDetector(
                            onTap: () => Navigator.of(context).push(
                              MaterialPageRoute(builder: (_) => GoalPathScreen(goal: goal)),
                            ),
                            child: GoalProgressCard(goal: goal, accentColor: widget.accentColor),
                          ),
                        ),
                      ],
                    ),
                  );
                },
              ),
            ...others.map((goal) => Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: GestureDetector(
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => GoalPathScreen(goal: goal)),
                    ),
                    child: GoalProgressCard(goal: goal, accentColor: widget.accentColor),
                  ),
                )),
          ],
        );
      },
    );
  }
}
