// ============================================================
// نقطة البداية — Skeleton فقط.
// ⚠️ لا شاشات فعلية لسا: التمثيل البصري (قناني أو غيرها) غير
// محسوم ولازم Concept Testing قبل أي بناء UI حقيقي (قسم 2 و 12).
// ============================================================

import 'package:flutter/material.dart';

void main() {
  runApp(const FinanceSavingsApp());
}

class FinanceSavingsApp extends StatelessWidget {
  const FinanceSavingsApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Finance & Savings Agent',
      home: Scaffold(
        appBar: AppBar(title: const Text('Finance & Savings Agent — Skeleton')),
        body: const Center(
          child: Text('لسا ما فيه شاشات فعلية — بانتظار Concept Testing'),
        ),
      ),
    );
  }
}
