import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../core/providers.dart';
import '../../core/dashboard_providers.dart';
import '../../core/api_client.dart';
import '../../models/category.dart';
import '../../models/sms_parse_result.dart';
import '../../theme/app_theme.dart';
import '../../theme/icon_mapper.dart';
import '../../widgets/income_allocation_sheet.dart';

class QuickLogScreen extends ConsumerStatefulWidget {
  const QuickLogScreen({super.key});

  @override
  ConsumerState<QuickLogScreen> createState() => _QuickLogScreenState();
}

class _QuickLogScreenState extends ConsumerState<QuickLogScreen> {
  String _type = 'expense'; // 'expense' أو 'income'
  final _amountController = TextEditingController();
  final _noteController = TextEditingController();
  Category? _selectedCategory;
  bool _isSubmitting = false;
  bool _isScanning = false;

  @override
  void initState() {
    super.initState();
    // نعيد بناء الشاشة كل ما المستخدم يكتب — عشان نفعّل/نعطّل زر الحفظ بشكل صحيح
    _amountController.addListener(() => setState(() {}));
    _noteController.addListener(() {
      // لو المستخدم بلّش يكتب ملاحظة، نلغي أي تصنيف كان محدد بالأيقونات —
      // عشان نضمن مسار واحد واضح (إما أيقونة، إما نص ذكي) بكل مرة
      if (_noteController.text.isNotEmpty && _selectedCategory != null) {
        setState(() => _selectedCategory = null);
      } else {
        setState(() {});
      }
    });
  }

  @override
  void dispose() {
    _amountController.dispose();
    _noteController.dispose();
    super.dispose();
  }

  bool get _canSubmit {
    final amount = double.tryParse(_amountController.text.trim());
    final hasValidAmount = amount != null && amount > 0;
    final hasCategoryOrNote =
        _selectedCategory != null || _noteController.text.trim().isNotEmpty;
    return hasValidAmount && hasCategoryOrNote;
  }

  void _selectCategory(Category category) {
    setState(() {
      _selectedCategory = category;
      _noteController.clear(); // نفس المنطق بالعكس — اختيار أيقونة بيلغي أي نص مكتوب
    });
  }

  String _formatAmount(double value) {
    return value == value.roundToDouble() ? value.toStringAsFixed(0) : value.toStringAsFixed(2);
  }

  Future<void> _scanReceipt() async {
    final source = await showModalBottomSheet<ImageSource>(
      context: context,
      builder: (_) => SafeArea(
        child: Wrap(
          children: [
            ListTile(
              leading: const Icon(Icons.camera_alt),
              title: const Text('صوّر فاتورة'),
              onTap: () => Navigator.pop(context, ImageSource.camera),
            ),
            ListTile(
              leading: const Icon(Icons.photo_library),
              title: const Text('اختر من المعرض'),
              onTap: () => Navigator.pop(context, ImageSource.gallery),
            ),
          ],
        ),
      ),
    );
    if (source == null || !mounted) return;

    final picked = await ImagePicker().pickImage(source: source, imageQuality: 85);
    if (picked == null || !mounted) return;

    setState(() => _isScanning = true);
    try {
      final result = await ref.read(transactionServiceProvider).scanReceipt(File(picked.path));

      if (!result.readable) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content: Text('ما قدرنا نقرأ الفاتورة بوضوح — جرب صورة أوضح أو عبّيها يدوي'),
          ));
        }
        return;
      }

      // نبحث عن التصنيف المقترح ضمن تصنيفات المستخدم الفعلية (رشيد ما بيخترع
      // id، بس منتأكد هون كمان قبل ما نعرضه بالواجهة)
      Category? matchedCategory;
      if (result.categoryId != null) {
        final categories = await ref.read(categoriesListProvider.future);
        for (final category in categories) {
          if (category.id == result.categoryId) {
            matchedCategory = category;
            break;
          }
        }
      }

      if (!mounted) return;
      setState(() {
        _type = 'expense'; // فاتورة دايمًا مصروف، مش دخل
        if (result.amount != null) _amountController.text = _formatAmount(result.amount!);
        // نفس منطق الشاشة الأصلي: مسار الأيقونة ومسار النص متبادلين، مش
        // مع بعض — لو عندنا تصنيف واثوق فيه منستخدمه (أسرع مراجعة)، وإلا
        // منعبّي النص الحر (اسم المحل) ويختار المستخدم تصنيف بنفسه
        if (matchedCategory != null) {
          _selectedCategory = matchedCategory;
          _noteController.clear();
        } else if (result.note != null) {
          _noteController.text = result.note!;
          _selectedCategory = null;
        }
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('قرأت الفاتورة — راجع البيانات قبل ما تحفظ 👀'),
        ));
      }
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _isScanning = false);
    }
  }

  Future<void> _parseSmsFromDialog() async {
    final controller = TextEditingController();
    final text = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('الصق نص الرسالة البنكية'),
        content: TextField(
          controller: controller,
          maxLines: 5,
          autofocus: true,
          decoration: const InputDecoration(
            hintText: 'مثال: Successfully received 4.500 JOD from...',
            border: OutlineInputBorder(),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: const Text('إلغاء'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(controller.text.trim()),
            child: const Text('حلّل'),
          ),
        ],
      ),
    );
    if (text == null || text.isEmpty || !mounted) return;

    try {
      final result = await ref.read(transactionServiceProvider).parseSms(text);
      if (!result.parsed) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content: Text('ما قدرنا نفهم هاي الرسالة — جرب تعبّي يدوي'),
          ));
        }
        return;
      }

      setState(() {
        if (result.type != null) _type = result.type!;
        if (result.amount != null) _amountController.text = _formatAmount(result.amount!);
        // النص هون وصف تحويل (زي "تحويل CliQ من ...")، مش اسم محل بالضرورة —
        // نسيبه بخانة الملاحظة والمستخدم يختار تصنيف مناسب بنفسه، بدل ما
        // نخمّن تصنيف غلط من نص مالي مجرد
        if (result.note != null) {
          _noteController.text = result.note!;
          _selectedCategory = null;
        }
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('فهمت الرسالة — راجع البيانات قبل ما تحفظ 👀'),
        ));
      }
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  Future<void> _submit() async {
    if (!_canSubmit) return;
    setState(() => _isSubmitting = true);

    try {
      final transactionService = ref.read(transactionServiceProvider);
      final result = await transactionService.quickLog(
        amount: double.parse(_amountController.text.trim()),
        type: _type,
        categoryId: _selectedCategory?.id,
        note: _noteController.text.trim().isEmpty ? null : _noteController.text.trim(),
      );

      // يحدّث الـ Dashboard تلقائيًا بمرة الفتح الجاية
      ref.invalidate(goalsListProvider);
      ref.invalidate(recentTransactionsProvider);

      if (!mounted) return;

      if (result.aiSuggested && result.category != null) {
        final confidencePercent = ((result.suggestionConfidence ?? 0) * 100).toStringAsFixed(0);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('رشيد صنّفها "${result.category!.name}" (ثقة $confidencePercent%)'),
        ));
      }

      // دخل جديد ولسا في مبلغ غير موزّع؟ نسأل المستخدم وين بدو يحطه قبل
      // ما نسكّر الشاشة — نفس القرار المتفق عليه: دايمًا نسأل صراحة.
      if (_type == 'income' && result.unallocatedAmount > 0) {
        await maybePromptIncomeAllocation(context, ref, result);
      }

      if (!mounted) return;
      Navigator.of(context).pop();
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _isSubmitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final categoriesAsync = ref.watch(categoriesListProvider);
    final user = ref.watch(currentUserProvider);
    final accentColor =
        user?.persona != null ? PersonaColors.fromKey(user!.persona!.key) : PersonaColors.energetic;

    return Scaffold(
      appBar: AppBar(
        title: const Text('تسجيل سريع'),
        actions: [
          IconButton(
            icon: _isScanning
                ? const SizedBox(
                    height: 20, width: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.camera_alt_outlined),
            tooltip: 'امسح فاتورة',
            onPressed: _isScanning ? null : _scanReceipt,
          ),
          IconButton(
            icon: const Icon(Icons.sms_outlined),
            tooltip: 'من رسالة بنكية',
            onPressed: _isScanning ? null : _parseSmsFromDialog,
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // --- Toggle مصروف / دخل ---
            Row(
              children: [
                Expanded(
                  child: _TypeToggleButton(
                    label: 'مصروف',
                    isSelected: _type == 'expense',
                    color: Colors.red.shade400,
                    onTap: () => setState(() {
                      _type = 'expense';
                      _selectedCategory = null;
                    }),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _TypeToggleButton(
                    label: 'دخل',
                    isSelected: _type == 'income',
                    color: Colors.green.shade400,
                    onTap: () => setState(() {
                      _type = 'income';
                      _selectedCategory = null;
                    }),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),

            // --- المبلغ ---
            TextField(
              controller: _amountController,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 32, fontWeight: FontWeight.bold),
              decoration: const InputDecoration(
                hintText: '0.0',
                border: InputBorder.none,
                suffixText: 'دينار',
              ),
            ),
            const Divider(height: 32),

            // --- مسار الأيقونات ---
            const Text('اختار تصنيف بضغطة وحدة',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
            const SizedBox(height: 12),
            categoriesAsync.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, _) => Text('ما قدرنا نجيب التصنيفات: $error'),
              data: (categories) {
                final relevant = categories
                    .where((c) => c.categoryType == _type || c.categoryType == 'both')
                    .toList();
                return Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: relevant.map((category) {
                    final isSelected = _selectedCategory?.id == category.id;
                    return InkWell(
                      onTap: () => _selectCategory(category),
                      borderRadius: BorderRadius.circular(14),
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 150),
                        width: 84,
                        padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 6),
                        decoration: BoxDecoration(
                          color: isSelected ? accentColor.withValues(alpha: 0.12) : Colors.grey.shade100,
                          borderRadius: BorderRadius.circular(14),
                          border: Border.all(
                            color: isSelected ? accentColor : Colors.transparent,
                            width: 2,
                          ),
                        ),
                        child: Column(
                          children: [
                            Icon(iconForKey(category.icon),
                                color: isSelected ? accentColor : Colors.black54),
                            const SizedBox(height: 6),
                            Text(category.name,
                                textAlign: TextAlign.center,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(fontSize: 11)),
                          ],
                        ),
                      ),
                    );
                  }).toList(),
                );
              },
            ),

            const SizedBox(height: 24),
            Row(children: const [
              Expanded(child: Divider()),
              Padding(padding: EdgeInsets.symmetric(horizontal: 8), child: Text('أو')),
              Expanded(child: Divider()),
            ]),
            const SizedBox(height: 16),

            // --- مسار النص الذكي ---
            const Text('اكتب وصف بسيط ورشيد بيصنّفها إلك',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
            const SizedBox(height: 12),
            TextField(
              controller: _noteController,
              textAlign: TextAlign.right,
              decoration: const InputDecoration(
                hintText: 'مثال: قهوة مع صاحبي',
              ),
            ),

            const SizedBox(height: 32),
            ElevatedButton(
              onPressed: (_canSubmit && !_isSubmitting) ? _submit : null,
              style: ElevatedButton.styleFrom(backgroundColor: accentColor),
              child: _isSubmitting
                  ? const SizedBox(
                      height: 20, width: 20,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                    )
                  : const Text('حفظ'),
            ),
          ],
        ),
      ),
    );
  }
}

class _TypeToggleButton extends StatelessWidget {
  final String label;
  final bool isSelected;
  final Color color;
  final VoidCallback onTap;

  const _TypeToggleButton({
    required this.label,
    required this.isSelected,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: BoxDecoration(
          color: isSelected ? color.withValues(alpha: 0.12) : Colors.grey.shade100,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: isSelected ? color : Colors.transparent, width: 2),
        ),
        child: Text(
          label,
          textAlign: TextAlign.center,
          style: TextStyle(
            fontWeight: FontWeight.bold,
            color: isSelected ? color : Colors.black54,
          ),
        ),
      ),
    );
  }
}
