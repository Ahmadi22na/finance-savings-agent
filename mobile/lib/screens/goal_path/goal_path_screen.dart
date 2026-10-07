import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../core/dashboard_providers.dart';
import '../../models/goal.dart';
import '../../theme/app_theme.dart';

/// شاشة مسار الهدف (Sprint 6 polish):
/// - دخول متحرك: الخط الملوّن بيتعبّى مرحلة بمرحلة، وكل مرحلة بتعمل "pop" وانفجار كونفيتي صغير.
/// - شخصية رشيد المختارة بتتحرك على المسار لآخر مرحلة وصلها المستخدم (وبتطفو بحركة خفيفة).
/// - نبض حول المرحلة الجاية، ومبلغ كل مرحلة مكتوب جنبها.
/// - عند مرحلة 10 المكتملة: احتفال كبير.
/// - لو الجهاز مفعّل "تقليل الحركة" بيتعرض كل شي مباشرة بدون أنيميشن.
/// ما في أي مكتبة جديدة: كله بالكود (AnimationController + CustomPainter + Ticker).
class GoalPathScreen extends ConsumerStatefulWidget {
  final Goal goal;
  const GoalPathScreen({super.key, required this.goal});

  @override
  ConsumerState<GoalPathScreen> createState() => _GoalPathScreenState();
}

class _GoalPathScreenState extends ConsumerState<GoalPathScreen> with TickerProviderStateMixin {
  static const int stageCount = 10;
  static const double _nodeSize = 56;
  static const double _verticalGap = 90;
  static const double _scrollPadding = 24;
  static const double _mascotHeight = 84;
  static const double _mascotWidth = 60;

  bool _isDeleting = false;

  late final AnimationController _entrance;
  late final AnimationController _idle;
  late final AnimationController _pulse;
  late final ScrollController _scroll = ScrollController();
  late final _ParticleSystem _particles = _ParticleSystem();
  late final Ticker _particleTicker;

  Duration _lastTick = Duration.zero;
  bool _started = false;
  bool _reduceMotion = false;
  bool _following = true;
  int _burstedStage = 0;
  Color _accent = PersonaColors.energetic;
  _PathLayout? _layout;

  @override
  void initState() {
    super.initState();
    final completed = _completedStagesCount();
    final entranceMs = math.min(2800, math.max(600, 600 + completed * 240));
    _entrance = AnimationController(vsync: this, duration: Duration(milliseconds: entranceMs));
    _idle = AnimationController(vsync: this, duration: const Duration(milliseconds: 1800));
    _pulse = AnimationController(vsync: this, duration: const Duration(milliseconds: 1500));
    _particleTicker = createTicker(_onParticleTick);

    _entrance.addListener(_onEntranceTick);
    _entrance.addStatusListener((status) {
      if (status != AnimationStatus.completed) return;
      final layout = _layout;
      if (layout != null && _completedStagesCount() >= stageCount) {
        _burst(layout.centerOf(stageCount), count: 46, big: true);
        HapticFeedback.mediumImpact();
      }
    });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_started) return;
    _started = true;

    _reduceMotion = MediaQuery.of(context).disableAnimations;
    if (_reduceMotion) {
      _burstedStage = _completedStagesCount();
      _entrance.value = 1;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _followStage(_shownStages);
      });
      return;
    }

    _idle.repeat(reverse: true);
    _pulse.repeat();
    _entrance.forward();
  }

  @override
  void dispose() {
    _entrance.dispose();
    _idle.dispose();
    _pulse.dispose();
    _particleTicker.dispose();
    _scroll.dispose();
    _particles.repaint.dispose();
    super.dispose();
  }

  // ---------------------------------------------------------------- الحالة

  /// عدد المراحل "المعروضة" الآن (كسري أثناء الأنيميشن، وبيوصل لعدد المراحل الحقيقي بالنهاية).
  double get _shownStages =>
      _completedStagesCount() * Curves.easeInOutCubic.transform(_entrance.value);

  int _completedStagesCount() {
    if (widget.goal.targetAmount <= 0) return 0;
    final ratio = widget.goal.currentAmount / widget.goal.targetAmount;
    return (ratio * stageCount).floor().clamp(0, stageCount);
  }

  String _amountForStage(int stage) {
    return (widget.goal.targetAmount / stageCount * stage).toStringAsFixed(0);
  }

  _PathLayout _layoutFor(double pathWidth) {
    final existing = _layout;
    if (existing != null && existing.width == pathWidth) return existing;
    final created = _PathLayout(
      stageCount: stageCount,
      nodeSize: _nodeSize,
      verticalGap: _verticalGap,
      width: pathWidth,
      height: (stageCount - 1) * _verticalGap + _nodeSize + _mascotHeight + 20,
    );
    _layout = created;
    return created;
  }

  // ------------------------------------------------------------- أنيميشن

  void _onEntranceTick() {
    final layout = _layout;
    if (layout == null) return;

    final shown = _shownStages;
    final reached = math.min(shown.floor(), stageCount);
    while (_burstedStage < reached) {
      _burstedStage++;
      _burst(layout.centerOf(_burstedStage), count: 12);
      HapticFeedback.selectionClick();
    }
    if (_following) _followStage(shown);
  }

  /// بيحرّك الـ scroll ليبقى رشيد بنص الشاشة تقريبًا أثناء تقدمه.
  void _followStage(double shown) {
    final layout = _layout;
    if (layout == null || !_scroll.hasClients || !_scroll.position.hasContentDimensions) return;
    final point = layout.pointAt(math.max(shown, 1.0));
    final fromBottom = layout.height - point.dy + _scrollPadding;
    final viewport = _scroll.position.viewportDimension;
    final raw = fromBottom - viewport / 2;
    final target = math.min(math.max(raw, 0.0), _scroll.position.maxScrollExtent);
    _scroll.jumpTo(target);
  }

  List<Color> get _confettiColors => [
        _accent,
        Colors.amber,
        Colors.pinkAccent,
        Colors.lightBlueAccent,
        Colors.greenAccent.shade400,
        Colors.deepPurpleAccent,
      ];

  void _burst(Offset origin, {required int count, bool big = false}) {
    if (_reduceMotion) return;
    _particles.burst(origin, count: count, colors: _confettiColors, big: big);
    if (!_particleTicker.isActive) {
      _lastTick = Duration.zero;
      _particleTicker.start();
    }
  }

  void _onParticleTick(Duration elapsed) {
    final dt = _lastTick == Duration.zero ? 0.016 : (elapsed - _lastTick).inMicroseconds / 1000000.0;
    _lastTick = elapsed;
    _particles.update(math.min(dt, 0.05));
    if (!_particles.isActive) {
      _particleTicker.stop();
      _lastTick = Duration.zero;
    }
  }

  // ----------------------------------------------------------------- واجهة

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(currentUserProvider);
    final accentColor =
        user?.persona != null ? PersonaColors.fromKey(user!.persona!.key) : PersonaColors.energetic;
    _accent = accentColor;
    final personaImage = user?.persona?.imageAssetPath;

    final completedStages = _completedStagesCount();
    final scheduleInfo = _scheduleStatus();
    final pathWidth = MediaQuery.of(context).size.width - 40;
    final layout = _layoutFor(pathWidth);

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.goal.title),
        actions: [
          IconButton(
            icon: const Icon(Icons.delete_outline),
            onPressed: _isDeleting ? null : () => _confirmDelete(context),
          ),
        ],
      ),
      body: Column(
        children: [
          _buildHeader(accentColor, scheduleInfo),
          Expanded(
            child: Listener(
              // أول ما المستخدم يلمس الشاشة منوقف التتبع التلقائي ونتركه يتحكم بالسحب
              onPointerDown: (_) => _following = false,
              child: SingleChildScrollView(
                controller: _scroll,
                reverse: true,
                padding: const EdgeInsets.symmetric(vertical: _scrollPadding),
                child: Center(
                  child: SizedBox(
                    width: pathWidth,
                    height: layout.height,
                    child: Stack(
                      clipBehavior: Clip.none,
                      children: [
                        Positioned.fill(
                          child: AnimatedBuilder(
                            animation: _entrance,
                            builder: (context, _) => _buildPathLayer(layout, accentColor, completedStages),
                          ),
                        ),
                        if (completedStages < stageCount) _buildPulseRing(layout, accentColor, completedStages),
                        _buildMascot(layout, accentColor, personaImage, completedStages),
                        Positioned.fill(
                          child: IgnorePointer(
                            child: CustomPaint(painter: _ParticlePainter(_particles)),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader(Color accentColor, _ScheduleInfo? scheduleInfo) {
    final target = widget.goal.targetAmount;
    final current = widget.goal.currentAmount;
    final remaining = math.max(0.0, target - current);
    final duration = _reduceMotion ? Duration.zero : _entrance.duration!;

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 8),
      child: TweenAnimationBuilder<double>(
        tween: Tween<double>(begin: 0, end: current),
        duration: duration,
        curve: Curves.easeInOutCubic,
        builder: (context, value, _) {
          final ratio = target > 0 ? math.min(1.0, math.max(0.0, value / target)) : 0.0;
          return Column(
            children: [
              Text(
                '${value.toStringAsFixed(0)} / ${target.toStringAsFixed(0)} دينار',
                style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 10),
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: LinearProgressIndicator(
                  value: ratio,
                  minHeight: 10,
                  backgroundColor: Colors.grey.shade300,
                  color: accentColor,
                ),
              ),
              const SizedBox(height: 6),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    '${(ratio * 100).round()}%',
                    style: TextStyle(color: accentColor, fontWeight: FontWeight.w700, fontSize: 13),
                  ),
                  Text(
                    remaining > 0 ? 'المتبقي ${remaining.toStringAsFixed(0)} دينار' : 'وصلت للهدف!',
                    style: TextStyle(color: Colors.grey.shade700, fontSize: 13),
                  ),
                ],
              ),
              if (scheduleInfo != null) ...[
                const SizedBox(height: 10),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                  decoration: BoxDecoration(
                    color: scheduleInfo.onTrack ? Colors.green.shade50 : Colors.orange.shade50,
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    scheduleInfo.label,
                    style: TextStyle(
                      color: scheduleInfo.onTrack ? Colors.green.shade800 : Colors.orange.shade800,
                      fontWeight: FontWeight.w600,
                      fontSize: 12,
                    ),
                  ),
                ),
              ],
            ],
          );
        },
      ),
    );
  }

  /// الخط + العقد + مبالغ المراحل. بيتعاد بناؤه فقط أثناء الأنيميشن الدخولي.
  Widget _buildPathLayer(_PathLayout layout, Color accentColor, int completedStages) {
    final shown = _shownStages;

    return Stack(
      clipBehavior: Clip.none,
      children: [
        CustomPaint(
          size: Size(layout.width, layout.height),
          painter: _PathPainter(layout: layout, shown: shown, accentColor: accentColor),
        ),
        for (int stage = 1; stage <= stageCount; stage++) ...[
          Positioned(
            left: layout.leftFor(stage),
            bottom: (stage - 1) * _verticalGap,
            child: _StageNode(
              stageNumber: stage,
              isCompleted: shown >= stage,
              isCurrent: stage == completedStages + 1,
              isFinal: stage == stageCount,
              accentColor: accentColor,
              size: _nodeSize,
              scale: _popScale(stage, shown),
              onTap: () => _onNodeTap(context, stage),
            ),
          ),
          Positioned(
            left: stage.isOdd ? _nodeSize + 10 : null,
            right: stage.isOdd ? null : _nodeSize + 10,
            bottom: (stage - 1) * _verticalGap + (_nodeSize - 20) / 2,
            child: Text(
              '${_amountForStage(stage)} دينار',
              style: TextStyle(
                fontSize: 12,
                fontWeight: shown >= stage ? FontWeight.w700 : FontWeight.w500,
                color: shown >= stage ? accentColor : Colors.grey.shade600,
              ),
            ),
          ),
        ],
      ],
    );
  }

  double _popScale(int stage, double shown) {
    final delta = shown - stage;
    if (delta < 0 || delta > 0.45) return 1.0;
    return 1.0 + 0.28 * math.sin(math.pi * delta / 0.45);
  }

  Widget _buildPulseRing(_PathLayout layout, Color accentColor, int completedStages) {
    final stage = completedStages + 1;
    return AnimatedBuilder(
      animation: _pulse,
      builder: (context, _) {
        final t = _pulse.value;
        final ringSize = _nodeSize + 28 * t;
        return Positioned(
          left: layout.leftFor(stage) - 14 * t,
          bottom: (stage - 1) * _verticalGap - 14 * t,
          child: IgnorePointer(
            child: Container(
              width: ringSize,
              height: ringSize,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                border: Border.all(color: accentColor.withValues(alpha: 0.5 * (1 - t)), width: 3),
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildMascot(_PathLayout layout, Color accentColor, String? personaImage, int completedStages) {
    return AnimatedBuilder(
      animation: Listenable.merge([_entrance, _idle]),
      builder: (context, _) {
        final point = layout.pointAt(_shownStages);
        final hop = _entrance.isAnimating
            ? math.sin(_entrance.value * math.pi * 2 * math.max(1, completedStages)).abs() * 12
            : 0.0;
        final bob = Curves.easeInOut.transform(_idle.value) * 5;
        final feetY = point.dy - _nodeSize / 2 + 6;

        final Widget mascot = personaImage == null
            ? Icon(Icons.savings, color: accentColor, size: 40)
            : Image.asset(
                personaImage,
                fit: BoxFit.contain,
                alignment: Alignment.bottomCenter,
                errorBuilder: (context, error, stack) => Icon(Icons.savings, color: accentColor, size: 40),
              );

        return Positioned(
          left: point.dx - _mascotWidth / 2,
          top: feetY - _mascotHeight - hop - bob,
          width: _mascotWidth,
          height: _mascotHeight,
          child: IgnorePointer(child: mascot),
        );
      },
    );
  }

  // --------------------------------------------------------------- تفاعل

  void _onNodeTap(BuildContext context, int stage) {
    HapticFeedback.lightImpact();
    final layout = _layout;
    if (stage <= _completedStagesCount()) {
      if (layout != null) _burst(layout.centerOf(stage), count: 16);
      _showMessage(context, _stageMessage(stage));
    } else {
      final needed = widget.goal.targetAmount / stageCount * stage - widget.goal.currentAmount;
      final rounded = math.max(1, needed.ceil());
      _showMessage(context, 'باقيلك $rounded دينار لتوصل للمرحلة $stage');
    }
  }

  String _stageMessage(int stageNumber) {
    const messages = [
      'بداية قوية! 🚀', 'ماشي منيح تابع! 💪', 'ربع الطريق خلص! 🎯', 'استمر، شكلك جاد! 🔥',
      'نص الطريق! هاي لحظة تستاهل وقفة 🎉', 'تجاوزت النص، الباقي أسهل 😎', 'قريب أكتر من بعيد هلأ ⭐',
      'كمان شوي ووصلت! 🏁', 'أنت عمليًا وصلت! 🙌', 'مبروك! هيك بيكون التوفير 🏆',
    ];
    final index = (stageNumber - 1).clamp(0, messages.length - 1);
    return messages[index];
  }

  void _showMessage(BuildContext context, String text) {
    final messenger = ScaffoldMessenger.of(context);
    messenger.hideCurrentSnackBar();
    messenger.showSnackBar(
      SnackBar(content: Text(text), duration: const Duration(seconds: 2)),
    );
  }

  _ScheduleInfo? _scheduleStatus() {
    if (widget.goal.deadline == null) return null;

    final totalDays = widget.goal.deadline!.difference(widget.goal.createdAt).inDays;
    if (totalDays <= 0) return null;

    final elapsedDays = DateTime.now().difference(widget.goal.createdAt).inDays.clamp(0, totalDays);
    final expectedStage = ((elapsedDays / totalDays) * stageCount).floor().clamp(0, stageCount);
    final actualStage = _completedStagesCount();
    final onTrack = actualStage >= expectedStage;

    return _ScheduleInfo(
      onTrack: onTrack,
      label: onTrack ? 'ماشي حسب الخطة 👍' : 'متأخر شوي عن الجدول الزمني ⏰',
    );
  }

  Future<void> _confirmDelete(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('حذف الهدف؟'),
        content: Text('رح تحذف "${widget.goal.title}" نهائيًا. هاد الإجراء ما بينرجع.'),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('إلغاء')),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('حذف', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;

    setState(() => _isDeleting = true);
    try {
      final goalService = ref.read(goalServiceProvider);
      await goalService.deleteGoal(widget.goal.id);
      ref.invalidate(goalsListProvider);
      if (context.mounted) Navigator.of(context).pop();
    } catch (e) {
      if (context.mounted) {
        setState(() => _isDeleting = false);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('ما قدرنا نحذف الهدف، جرب كمان شوي')),
        );
      }
    }
  }
}

class _ScheduleInfo {
  final bool onTrack;
  final String label;
  _ScheduleInfo({required this.onTrack, required this.label});
}

/// هندسة المسار (مواقع العقد ومقاطع الخط) — مشتركة بين الرسم وموقع الشخصية والكونفيتي.
/// كل الإحداثيات فعلية (x من اليسار) بغض النظر عن اتجاه RTL، متل ما كان بالنسخة السابقة.
class _PathLayout {
  final int stageCount;
  final double nodeSize;
  final double verticalGap;
  final double width;
  final double height;

  _PathLayout({
    required this.stageCount,
    required this.nodeSize,
    required this.verticalGap,
    required this.width,
    required this.height,
  });

  late final List<Path> segments = List<Path>.generate(stageCount - 1, (i) => _buildSegment(i + 1));

  double leftFor(int stage) => stage.isOdd ? 0.0 : (width - nodeSize);

  Offset centerOf(int stage) {
    final x = leftFor(stage) + nodeSize / 2;
    final yFromBottom = (stage - 1) * verticalGap + nodeSize / 2;
    return Offset(x, height - yFromBottom);
  }

  /// مقطع الخط من المرحلة [stage] للمرحلة اللي بعدها.
  Path _buildSegment(int stage) {
    final start = centerOf(stage);
    final end = centerOf(stage + 1);
    return Path()
      ..moveTo(start.dx, start.dy)
      ..cubicTo(start.dx, start.dy - verticalGap / 2, end.dx, end.dy + verticalGap / 2, end.dx, end.dy);
  }

  /// نقطة على المسار عند قيمة مراحل كسرية (مثلاً 3.5 = نص المسافة بين المرحلة 3 و4).
  Offset pointAt(double stageValue) {
    if (stageValue <= 1) return centerOf(1);
    int stage = stageValue.floor();
    double fraction = stageValue - stage;
    if (stage >= stageCount) {
      stage = stageCount - 1;
      fraction = 1.0;
    }
    final metric = segments[stage - 1].computeMetrics().first;
    final tangent = metric.getTangentForOffset(metric.length * fraction);
    return tangent?.position ?? centerOf(stage);
  }
}

class _PathPainter extends CustomPainter {
  final _PathLayout layout;
  final double shown;
  final Color accentColor;

  _PathPainter({required this.layout, required this.shown, required this.accentColor});

  @override
  void paint(Canvas canvas, Size size) {
    final basePaint = Paint()
      ..color = Colors.grey.shade300
      ..strokeWidth = 8
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    final progressPaint = Paint()
      ..color = accentColor
      ..strokeWidth = 8
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    for (final segment in layout.segments) {
      canvas.drawPath(segment, basePaint);
    }

    for (int stage = 1; stage < layout.stageCount; stage++) {
      final fraction = math.min(1.0, math.max(0.0, shown - stage));
      if (fraction <= 0) continue;
      final metric = layout.segments[stage - 1].computeMetrics().first;
      canvas.drawPath(metric.extractPath(0, metric.length * fraction), progressPaint);
    }
  }

  @override
  bool shouldRepaint(covariant _PathPainter oldDelegate) {
    return oldDelegate.shown != shown ||
        oldDelegate.accentColor != accentColor ||
        oldDelegate.layout != layout;
  }
}

class _StageNode extends StatelessWidget {
  final int stageNumber;
  final bool isCompleted;
  final bool isCurrent;
  final bool isFinal;
  final Color accentColor;
  final double size;
  final double scale;
  final VoidCallback onTap;

  const _StageNode({
    required this.stageNumber,
    required this.isCompleted,
    required this.isCurrent,
    required this.isFinal,
    required this.accentColor,
    required this.size,
    required this.scale,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final borderColor = isCurrent || isCompleted ? accentColor : Colors.grey.shade300;

    final Widget content;
    if (isFinal) {
      content = Icon(
        isCompleted ? Icons.emoji_events : Icons.emoji_events_outlined,
        color: isCompleted ? Colors.white : Colors.grey.shade500,
      );
    } else if (isCompleted) {
      content = const Icon(Icons.check, color: Colors.white);
    } else {
      content = Text(
        '$stageNumber',
        style: TextStyle(color: Colors.grey.shade500, fontWeight: FontWeight.bold),
      );
    }

    return Semantics(
      button: true,
      label: 'المرحلة $stageNumber ${isCompleted ? 'مكتملة' : 'لم تكتمل بعد'}',
      child: Transform.scale(
        scale: scale,
        child: GestureDetector(
          onTap: onTap,
          child: Container(
            width: size,
            height: size,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: isCompleted ? accentColor : Colors.white,
              border: Border.all(color: borderColor, width: isCurrent ? 3 : 2),
              boxShadow: [
                BoxShadow(
                  color: isCurrent ? accentColor.withValues(alpha: 0.35) : Colors.black12,
                  blurRadius: isCurrent ? 10 : 4,
                  spreadRadius: isCurrent ? 2 : 0,
                ),
              ],
            ),
            child: Center(child: content),
          ),
        ),
      ),
    );
  }
}

// ------------------------------------------------------------------ كونفيتي

class _Particle {
  Offset position;
  Offset velocity;
  double rotation;
  final double spin;
  final double size;
  final Color color;
  double life;

  _Particle({
    required this.position,
    required this.velocity,
    required this.rotation,
    required this.spin,
    required this.size,
    required this.color,
    required this.life,
  });
}

class _ParticleSystem {
  final List<_Particle> particles = [];
  final ValueNotifier<int> repaint = ValueNotifier<int>(0);
  final math.Random _random = math.Random();

  bool get isActive => particles.isNotEmpty;

  void burst(Offset origin, {required int count, required List<Color> colors, bool big = false}) {
    for (int i = 0; i < count; i++) {
      final angle = _random.nextDouble() * math.pi * 2;
      final speed = (big ? 180.0 : 120.0) + _random.nextDouble() * (big ? 340.0 : 200.0);
      particles.add(
        _Particle(
          position: origin,
          velocity: Offset(math.cos(angle) * speed, math.sin(angle) * speed - (big ? 160.0 : 90.0)),
          rotation: _random.nextDouble() * math.pi * 2,
          spin: (_random.nextDouble() - 0.5) * 14,
          size: 6 + _random.nextDouble() * 6,
          color: colors[_random.nextInt(colors.length)],
          life: 0.9 + _random.nextDouble() * 0.7,
        ),
      );
    }
  }

  void update(double dt) {
    for (final p in particles) {
      p.velocity = Offset(p.velocity.dx * 0.985, p.velocity.dy + 520 * dt);
      p.position = p.position + p.velocity * dt;
      p.rotation += p.spin * dt;
      p.life -= dt;
    }
    particles.removeWhere((p) => p.life <= 0);
    repaint.value++;
  }
}

class _ParticlePainter extends CustomPainter {
  final _ParticleSystem system;

  _ParticlePainter(this.system) : super(repaint: system.repaint);

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint();
    for (final p in system.particles) {
      final fade = math.min(1.0, p.life / 0.4);
      paint.color = p.color.withValues(alpha: fade);
      canvas.save();
      canvas.translate(p.position.dx, p.position.dy);
      canvas.rotate(p.rotation);
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromCenter(center: Offset.zero, width: p.size, height: p.size * 0.55),
          const Radius.circular(1.5),
        ),
        paint,
      );
      canvas.restore();
    }
  }

  @override
  bool shouldRepaint(covariant _ParticlePainter oldDelegate) => false;
}
