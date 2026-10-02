import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'providers.dart';
import '../models/persona.dart';



final personasListProvider = FutureProvider<List<Persona>>((ref) async {
  final onboardingService = ref.watch(onboardingServiceProvider);
  return onboardingService.listPersonas();
});
