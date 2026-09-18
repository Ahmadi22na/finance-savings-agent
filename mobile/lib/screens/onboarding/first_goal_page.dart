import 'package:flutter/material.dart';

import '../../widgets/app_text_field.dart';

class FirstGoalPage extends StatelessWidget {
  final TextEditingController titleController;
  final TextEditingController amountController;

  const FirstGoalPage({
    super.key,
    required this.titleController,
    required this.amountController,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text('شو أول هدف بدك توفر إله؟',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          const Text('تقدر تضيف أهداف تانية لاحقًا بأي وقت',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.black54)),
          const SizedBox(height: 32),
          AppTextField(
            controller: titleController,
            label: 'اسم الهدف (مثال: رحلة سفر)',
          ),
          const SizedBox(height: 16),
          AppTextField(
            controller: amountController,
            label: 'المبلغ المستهدف (دينار)',
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
          ),
        ],
      ),
    );
  }
}
