import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../core/api_client.dart';
import '../../core/onboarding_providers.dart';
import '../../models/persona.dart';
import '../dashboard/dashboard_screen.dart';
import 'persona_select_page.dart';
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
  String _selectedIncomeType = 'variable'; // الافتراضي: جمهورنا دخله غير منتظم
  final _goalTitleController = TextEditingController();
  final _goalAmountController = TextEditingController();

  // خطوتين فقط: (1) الشخصية + نوع الدخل (مختارين مسبقًا)، (2) هدف اختياري. المستخدم ممكن يوصل بدون أي إدخال.
  static const int _totalPages = 2;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _preselectDefaultPersona(ref.read(personasListProvider));
    });

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



  /// اختيار الشخصية الافتراضية أول ما تنحمّل القائمة، عشان زر "التالي" يشتغل فورًا.
  void _preselectDefaultPersona(AsyncValue<List<Persona>> personasAsync) {
    final personas = personasAsync.value;
    if (_selectedPersona != null || personas == null || personas.isEmpty) return;
    final defaultPersona = personas.firstWhere((p) => p.key == 'energetic', orElse: () => personas.first);
    setState(() => _selectedPersona = defaultPersona);
  }

  bool get _hasGoalInput =>
      _goalTitleController.text.trim().isNotEmpty || _goalAmountController.text.trim().isNotEmpty;

  bool get _goalIsValid {
    final title = _goalTitleController.text.trim();
    final amount = double.tryParse(_goalAmountController.text.trim());
    return title.length >= 2 && amount != null && amount > 0;
  }

  bool get _canProceed {
    switch (_currentPage) {
      case 0:
        return _selectedPersona != null;
      case 1:
        // الهدف اختياري: فاضي = تخطّي، وإذا انكتب شي لازم يكتمل (عنوان + مبلغ صحيح)
        return !_hasGoalInput || _goalIsValid;
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
        incomeType: _selectedIncomeType,
        personaId: _selectedPersona!.id,
        goalTitle: _goalIsValid ? _goalTitleController.text.trim() : null,
        goalTargetAmount: _goalIsValid ? double.parse(_goalAmountController.text.trim()) : null,
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
    ref.listen<AsyncValue<List<Persona>>>(
      personasListProvider,
      (previous, next) => _preselectDefaultPersona(next),
    );

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [

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
                physics: const NeverScrollableScrollPhysics(),
                onPageChanged: (index) => setState(() => _currentPage = index),
                children: [
                  PersonaSelectPage(
                    selectedPersona: _selectedPersona,
                    onSelect: (persona) => setState(() => _selectedPersona = persona),
                    selectedIncomeType: _selectedIncomeType,
                    onSelectIncomeType: (type) => setState(() => _selectedIncomeType = type),
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
                          : Text(_currentPage == _totalPages - 1
                              ? (_hasGoalInput ? 'يلا نبدأ' : 'ابدأ بدون هدف')
                              : 'التالي'),
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
