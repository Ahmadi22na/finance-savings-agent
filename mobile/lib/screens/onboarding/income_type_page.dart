import 'package:flutter/material.dart';

import '../../widgets/selectable_card.dart';

class IncomeTypePage extends StatelessWidget {
  final String? selectedType;
  final ValueChanged<String> onSelect;

  const IncomeTypePage({
    super.key,
    required this.selectedType,
    required this.onSelect,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text('شو يشبه دخلك أكتر؟',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          const Text('هيك رشيد بيحكي معك بأسلوب يناسب وضعك',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.black54)),
          const SizedBox(height: 32),
          SelectableCard(
            isSelected: selectedType == 'fixed',
            onTap: () => onSelect('fixed'),
            child: const Row(
              children: [
                Icon(Icons.calendar_month),
                SizedBox(width: 12),
                Text('دخل ثابت شهريًا', style: TextStyle(fontSize: 15)),
              ],
            ),
          ),
          const SizedBox(height: 12),
          SelectableCard(
            isSelected: selectedType == 'variable',
            onTap: () => onSelect('variable'),
            child: const Row(
              children: [
                Icon(Icons.bar_chart),
                SizedBox(width: 12),
                Text('دخل متغيّر (فريلانس / يومي)', style: TextStyle(fontSize: 15)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
