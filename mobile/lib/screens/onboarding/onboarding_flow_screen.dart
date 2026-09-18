import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../core/api_client.dart';
import '../../models/persona.dart';
import '../dashboard/dashboard_screen.dart';
import 'persona_select_page.dart';
import 'income_type_page.dart';
import 'first_goal_page.dart';

class OnboardingFlowScreen extends ConsumerStatefulWidget {
  const OnboardingFlowScreen({super.key});

  @override
  ConsumerState<OnboardingFlowScreen> createState() => _OnboardingFlowScreenState();
}

class _OnboardingFlowScreenState extends ConsumerState<OnboardingFlowScreen> {
  final _pageController = PageController();
  int _currentPage = 0;
  bool _isSubmitting = false;

  Persona? _selectedPersona;
  String? _selectedIncomeType;
  final _goalTitleController = TextEditingController();
  final _goalAmountController = TextEditingController();

  static const int _totalPages = 3;

  @override
  void initState() {
    super.initState();
    // بدون هالمستمعين، الشاشة ما "بتعرف" إنه المستخدم كتب شي بحقول الهدف
    // والمبلغ، فزر "يلا نبدأ" كان يضل معطّل حتى لو الحقول معبّية صح —
    // setState(() {}) هون بس بيخلي build() يعيد فحص _canProceed من جديد.
    _goalTitleController.addListener(() => setState(() {}));
    _goalAmountController.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _pageController.dispose();
    _goalTitleController.dispose();
    _goalAmountController.dispose();
    super.dispose();
  }

  /// هل يقدر المستخدم يكمل من الصفحة الحالية؟ نفس فكرة الـ Validation
  /// بالـ Backend (model_validator بـ OnboardingComplete) بس على مستوى كل خطوة.
  bool get _canProceed {
    switch (_currentPage) {
      case 0:
        return _selectedPersona != null;
      case 1:
        return _selectedIncomeType != null;
      case 2:
        final title = _goalTitleController.text.trim();
        final amount = double.tryParse(_goalAmountController.text.trim());
        return title.length >= 2 && amount != null && amount > 0;
      default:
        return false;
    }
  }

  void _goNext() {
    if (!_canProceed) return;
    if (_currentPage == _totalPages - 1) {
      _submit();
      return;
    }
    _pageController.nextPage(
      duration: const Duration(milliseconds: 250),
      curve: Curves.easeInOut,
    );
  }

  void _goBack() {
    if (_currentPage == 0) return;
    _pageController.previousPage(
      duration: const Duration(milliseconds: 250),
      curve: Curves.easeInOut,
    );
  }

  Future<void> _submit() async {
    setState(() => _isSubmitting = true);
    try {
      final onboardingService = ref.read(onboardingServiceProvider);
      final updatedUser = await onboardingService.completeOnboarding(
        incomeType: _selectedIncomeType!,
        personaId: _selectedPersona!.id,
        goalTitle: _goalTitleController.text.trim(),
        goalTargetAmount: double.parse(_goalAmountController.text.trim()),
      );

      ref.read(currentUserProvider.notifier).state = updatedUser;

      if (!mounted) return;
      Navigator.of(context).pushAndRemoveUntil(
        MaterialPageRoute(builder: (_) => const DashboardScreen()),
        (route) => false,
      );
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _isSubmitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            // مؤشر التقدم البسيط (3 نقاط) — نفس فكرة المعاينة الأولى يلي عرضناها بالبداية
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 16),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: List.generate(_totalPages, (i) {
                  final isActive = i == _currentPage;
                  return AnimatedContainer(
                    duration: const Duration(milliseconds: 200),
                    margin: const EdgeInsets.symmetric(horizontal: 4),
                    width: isActive ? 24 : 8,
                    height: 8,
                    decoration: BoxDecoration(
                      color: isActive ? Colors.black87 : Colors.grey.shade300,
                      borderRadius: BorderRadius.circular(4),
                    ),
                  );
                }),
              ),
            ),
            Expanded(
              child: PageView(
                controller: _pageController,
                physics: const NeverScrollableScrollPhysics(), // التنقل بس عبر الأزرار، مش سحب
                onPageChanged: (index) => setState(() => _currentPage = index),
                children: [
                  PersonaSelectPage(
                    selectedPersona: _selectedPersona,
                    onSelect: (persona) => setState(() => _selectedPersona = persona),
                  ),
                  IncomeTypePage(
                    selectedType: _selectedIncomeType,
                    onSelect: (type) => setState(() => _selectedIncomeType = type),
                  ),
                  FirstGoalPage(
                    titleController: _goalTitleController,
                    amountController: _goalAmountController,
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(24),
              child: Row(
                children: [
                  if (_currentPage > 0)
                    Expanded(
                      child: OutlinedButton(
                        onPressed: _isSubmitting ? null : _goBack,
                        child: const Text('السابق'),
                      ),
                    ),
                  if (_currentPage > 0) const SizedBox(width: 12),
                  Expanded(
                    flex: 2,
                    child: ElevatedButton(
                      onPressed: (_canProceed && !_isSubmitting) ? _goNext : null,
                      child: _isSubmitting
                          ? const SizedBox(
                              height: 20, width: 20,
                              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                            )
                          : Text(_currentPage == _totalPages - 1 ? 'يلا نبدأ' : 'التالي'),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
