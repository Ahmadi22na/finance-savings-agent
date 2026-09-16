import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../core/dashboard_providers.dart';
import '../../core/api_client.dart';
import '../../theme/app_theme.dart';
import '../../widgets/goal_progress_card.dart';
import '../../widgets/transaction_tile.dart';
import '../auth/login_screen.dart';
import '../quick_log/quick_log_screen.dart';

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);
    final goalsAsync = ref.watch(goalsListProvider);
    final transactionsAsync = ref.watch(recentTransactionsProvider);
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
          // إعادة تحميل الأهداف والمعاملات — بينفع لما تسجّل معاملة جديدة
          // وتحب تتأكد إنها انعكست بالـ Dashboard
          ref.invalidate(goalsListProvider);
          ref.invalidate(recentTransactionsProvider);
        },
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            const Text('أهدافك', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            goalsAsync.when(
              loading: () => const Center(
                child: Padding(
                  padding: EdgeInsets.all(24),
                  child: CircularProgressIndicator(),
                ),
              ),
              error: (error, _) => Text('ما قدرنا نجيب أهدافك: $error'),
              data: (goals) {
                if (goals.isEmpty) {
                  return const Padding(
                    padding: EdgeInsets.symmetric(vertical: 16),
                    child: Text('ما عندك أهداف بعد', style: TextStyle(color: Colors.black54)),
                  );
                }
                return Column(
                  children: goals
                      .map((goal) => Padding(
                            padding: const EdgeInsets.only(bottom: 12),
                            child: GoalProgressCard(goal: goal, accentColor: accentColor),
                          ))
                      .toList(),
                );
              },
            ),
            const SizedBox(height: 28),
            const Text('آخر المعاملات', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
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
            const SizedBox(height: 80), // مساحة إضافية تحت عشان الـ FAB ما يغطي آخر عنصر
          ],
        ),
      ),
    );
  }
}
