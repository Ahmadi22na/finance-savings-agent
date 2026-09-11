import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/onboarding_providers.dart';
import '../../models/persona.dart';
import '../../theme/app_theme.dart';
import '../../widgets/selectable_card.dart';

class PersonaSelectPage extends ConsumerWidget {
  final Persona? selectedPersona;
  final ValueChanged<Persona> onSelect;

  const PersonaSelectPage({
    super.key,
    required this.selectedPersona,
    required this.onSelect,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final personasAsync = ref.watch(personasListProvider);

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text('مين بدك يرافقك بهاي الرحلة؟',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          const Text('اختار شخصية رشيد يلي بتشبهك أكتر',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.black54)),
          const SizedBox(height: 24),
          Expanded(
            child: personasAsync.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, _) => Center(
                child: Text('ما قدرنا نجيب الشخصيات، تأكد من اتصال السيرفر\n$error',
                    textAlign: TextAlign.center),
              ),
              data: (personas) => ListView.separated(
                itemCount: personas.length,
                separatorBuilder: (_, __) => const SizedBox(height: 12),
                itemBuilder: (context, index) {
                  final persona = personas[index];
                  final isSelected = selectedPersona?.id == persona.id;
                  final color = PersonaColors.fromKey(persona.key);

                  return SelectableCard(
                    isSelected: isSelected,
                    selectedColor: color,
                    onTap: () => onSelect(persona),
                    child: Row(
                      children: [
                        SizedBox(
                          height: 90,
                          width: 70,
                          child: Image.asset(persona.imageAssetPath, fit: BoxFit.contain),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(persona.displayName,
                                  style: TextStyle(
                                      fontSize: 17,
                                      fontWeight: FontWeight.bold,
                                      color: color)),
                              const SizedBox(height: 4),
                              Text(persona.tagline,
                                  style: const TextStyle(color: Colors.black54, fontSize: 13)),
                            ],
                          ),
                        ),
                        if (isSelected) Icon(Icons.check_circle, color: color),
                      ],
                    ),
                  );
                },
              ),
            ),
          ),
        ],
      ),
    );
  }
}
