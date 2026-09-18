import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'providers.dart';
import '../models/persona.dart';

/// FutureProvider بسيط — يجيب قائمة الشخصيات مرة وحدة ويخزّنها (Riverpod
/// بيعمل Cache تلقائي). شاشة اختيار الشخصية بتستهلكه مباشرة بـ ref.watch.
final personasListProvider = FutureProvider<List<Persona>>((ref) async {
  final onboardingService = ref.watch(onboardingServiceProvider);
  return onboardingService.listPersonas();
});
