import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/onboarding_providers.dart';
import '../../models/persona.dart';
import '../../theme/app_theme.dart';
import '../../widgets/selectable_card.dart';

/// الخطوة الأولى بالـ Onboarding: شخصية رشيد + نوع الدخل بصفحة وحدة. الاثنين مختارين مسبقًا (افتراضي)،
/// فالمستخدم بيقدر يضغط "التالي" مباشرة بدون أي إدخال.
class PersonaSelectPage extends ConsumerWidget {
  final Persona? selectedPersona;
  final ValueChanged<Persona> onSelect;
  final String selectedIncomeType;
  final ValueChanged<String> onSelectIncomeType;

  const PersonaSelectPage({
    super.key,
    required this.selectedPersona,
    required this.onSelect,
    required this.selectedIncomeType,
    required this.onSelectIncomeType,
  });

  Widget _personaCard(Persona persona) {
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
                    style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold, color: color)),
                const SizedBox(height: 4),
                Text(persona.tagline, style: const TextStyle(color: Colors.black54, fontSize: 13)),
              ],
            ),
          ),
          if (isSelected) Icon(Icons.check_circle, color: color),
        ],
      ),
    );
  }

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
          const Text('اختار شخصية رشيد يلي بتشبهك أكتر (وتقدر تكمّل مباشرة بالاختيار الجاهز)',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.black54)),
          const SizedBox(height: 20),
          Expanded(
            child: personasAsync.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, _) => Center(
                child: Text('ما قدرنا نجيب الشخصيات، تأكد من اتصال السيرفر\n$error',
                    textAlign: TextAlign.center),
              ),
              data: (personas) => ListView(
                children: [
                  for (final persona in personas) ...[
                    _personaCard(persona),
                    const SizedBox(height: 12),
                  ],
                  const SizedBox(height: 12),
                  const Text('شو يشبه دخلك؟', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 4),
                  const Text('هيك رشيد بيحكي معك بأسلوب يناسب وضعك',
                      style: TextStyle(color: Colors.black54, fontSize: 12)),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      ChoiceChip(
                        avatar: const Icon(Icons.calendar_month, size: 16),
                        label: const Text('دخل ثابت شهريًا'),
                        selected: selectedIncomeType == 'fixed',
                        onSelected: (_) => onSelectIncomeType('fixed'),
                      ),
                      ChoiceChip(
                        avatar: const Icon(Icons.bar_chart, size: 16),
                        label: const Text('دخل متغيّر (فريلانس / يومي)'),
                        selected: selectedIncomeType == 'variable',
                        onSelected: (_) => onSelectIncomeType('variable'),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
