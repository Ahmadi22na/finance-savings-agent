import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'providers.dart';
import '../models/goal.dart';
import '../models/transaction.dart';
import '../models/category.dart';



final goalsListProvider = FutureProvider.autoDispose<List<Goal>>((ref) async {
  final goalService = ref.watch(goalServiceProvider);
  return goalService.listGoals();
});

final recentTransactionsProvider = FutureProvider.autoDispose<List<Transaction>>((ref) async {
  final transactionService = ref.watch(transactionServiceProvider);
  return transactionService.listTransactions(limit: 10);
});


final categoriesListProvider = FutureProvider.autoDispose<List<Category>>((ref) async {
  final categoryService = ref.watch(categoryServiceProvider);
  return categoryService.listCategories();
});
