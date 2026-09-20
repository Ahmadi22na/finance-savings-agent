import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'providers.dart';
import '../models/agent_action.dart';

/// قراءة بس (بدون AI) — آمنة تتحدّث بكل ما تفتح الـ Dashboard، مافيها أي تكلفة.
final pendingActionsProvider = FutureProvider.autoDispose<List<AgentAction>>((ref) async {
  final agentService = ref.watch(agentServiceProvider);
  return agentService.listPendingActions();
});
