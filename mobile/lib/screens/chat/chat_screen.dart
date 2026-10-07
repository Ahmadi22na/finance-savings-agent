import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../core/api_client.dart';
import '../../models/chat_message.dart';
import '../../theme/app_theme.dart';

/// أسئلة مقترحة تظهر لما تكون المحادثة فاضية (بتنبعت كرسالة عادية عند الضغط).
const _suggestedPrompts = [
  'كم باقيلي عشان أوصل لهدفي؟',
  'كيف كانت مصاريفي هالأسبوع؟',
  'اعطيني نصيحة أوفّر فيها اليوم',
  'اجاني 25 دينار اليوم',
];

class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final _messages = <ChatMessage>[];
  // الفهارس اللي انعرضت قبل (عشان الأنيميشن يشتغل مرة وحدة بس لكل رسالة، مش كل ما نعمل scroll)
  final _animatedIndexes = <int>{};
  final _textController = TextEditingController();
  final _scrollController = ScrollController();
  bool _isSending = false;
  bool _checkedNudge = false;
  bool _hasText = false;
  int? _speakingIndex;

  @override
  void initState() {
    super.initState();
    _textController.addListener(_onTextChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) => _checkForNudge());
  }

  @override
  void dispose() {
    ref.read(ttsServiceProvider).stop();
    _textController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _onTextChanged() {
    final hasText = _textController.text.trim().isNotEmpty;
    if (hasText != _hasText) setState(() => _hasText = hasText);
  }

  Future<void> _toggleSpeak(int index, String text) async {
    final tts = ref.read(ttsServiceProvider);

    if (_speakingIndex == index) {
      await tts.stop();
      if (mounted) setState(() => _speakingIndex = null);
      return;
    }

    setState(() => _speakingIndex = index);
    final personaKey = ref.read(currentUserProvider)?.persona?.key ?? 'business';
    final started = await tts.speak(
      text,
      personaKey: personaKey,
      onDone: () {
        if (mounted) setState(() => _speakingIndex = null);
      },
    );

    if (!started && mounted) {
      setState(() => _speakingIndex = null);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('جهازك ما فيه صوت عربي مثبت — فعّله من إعدادات النظام')),
      );
    }
  }

  Future<void> _checkForNudge() async {
    try {
      final agentService = ref.read(agentServiceProvider);
      final nudge = await agentService.checkNudge();
      if (nudge != null && mounted) {
        setState(() {
          _messages.add(ChatMessage(text: nudge, isFromUser: false, isNudge: true));
        });
        _scrollToBottom();
      }
    } catch (_) {
      // الـ nudge اختياري — لو فشل ما منعطّل المحادثة
    } finally {
      if (mounted) setState(() => _checkedNudge = true);
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _send() => _sendText(_textController.text);

  Future<void> _sendText(String raw) async {
    final text = raw.trim();
    if (text.isEmpty || _isSending) return;

    HapticFeedback.lightImpact();
    setState(() {
      _messages.add(ChatMessage(text: text, isFromUser: true));
      _isSending = true;
    });
    _textController.clear();
    _scrollToBottom();

    try {
      final agentService = ref.read(agentServiceProvider);
      final reply = await agentService.sendMessage(text);
      if (!mounted) return;
      setState(() {
        _messages.add(ChatMessage(text: reply, isFromUser: false));
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _messages.add(ChatMessage(text: e.message, isFromUser: false));
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _messages.add(ChatMessage(text: 'صار في مشكلة بالاتصال، جرب كمان شوي 🙏', isFromUser: false));
      });
    } finally {
      if (mounted) setState(() => _isSending = false);
      _scrollToBottom();
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(currentUserProvider);
    final persona = user?.persona;
    final accentColor = persona != null ? PersonaColors.fromKey(persona.key) : PersonaColors.energetic;
    final personaName = persona?.displayName ?? 'رشيد';
    final personaImage = persona?.imageAssetPath;

    return Scaffold(
      appBar: AppBar(
        titleSpacing: 0,
        title: Row(
          children: [
            CircleAvatar(
              radius: 18,
              backgroundColor: accentColor.withValues(alpha: 0.15),
              child: personaImage != null
                  ? Padding(
                      padding: const EdgeInsets.all(3),
                      child: Image.asset(personaImage, fit: BoxFit.contain),
                    )
                  : Icon(Icons.savings, color: accentColor, size: 20),
            ),
            const SizedBox(width: 10),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(personaName, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                Text(
                  _isSending ? 'عم يكتب...' : 'جاهز لمساعدتك',
                  style: const TextStyle(fontSize: 11, color: Colors.black54),
                ),
              ],
            ),
          ],
        ),
      ),
      body: Column(
        children: [
          Expanded(
            child: GestureDetector(
              behavior: HitTestBehavior.translucent,
              onTap: () => FocusScope.of(context).unfocus(),
              child: _buildMessagesArea(accentColor, personaName, personaImage),
            ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _textController,
                      textAlign: TextAlign.right,
                      textInputAction: TextInputAction.send,
                      onSubmitted: (_) => _send(),
                      decoration: const InputDecoration(
                        hintText: 'اكتب رسالتك...',
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton.filled(
                    style: IconButton.styleFrom(
                      backgroundColor: accentColor,
                      disabledBackgroundColor: Colors.grey.shade300,
                    ),
                    onPressed: (_isSending || !_hasText) ? null : _send,
                    icon: const Icon(Icons.send),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMessagesArea(Color accentColor, String personaName, String? personaImage) {
    if (!_checkedNudge && _messages.isEmpty) {
      return Center(child: CircularProgressIndicator(color: accentColor));
    }

    if (_messages.isEmpty) {
      return _EmptyState(
        accentColor: accentColor,
        personaName: personaName,
        personaImagePath: personaImage,
        prompts: _suggestedPrompts,
        onPrompt: _sendText,
      );
    }

    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.all(16),
      itemCount: _messages.length + (_isSending ? 1 : 0),
      itemBuilder: (context, index) {
        if (index == _messages.length) {
          return _TypingBubble(accentColor: accentColor, personaImagePath: personaImage);
        }

        final message = _messages[index];
        final animate = _animatedIndexes.add(index);
        return _AnimatedEntrance(
          animate: animate,
          child: _ChatBubble(
            message: message,
            accentColor: accentColor,
            personaImagePath: personaImage,
            isSpeaking: _speakingIndex == index,
            onToggleSpeak: message.isFromUser ? null : () => _toggleSpeak(index, message.text),
          ),
        );
      },
    );
  }
}

/// ظهور ناعم للرسالة الجديدة (fade + انزلاق بسيط)، وبيتعطّل لو الجهاز مفعّل "تقليل الحركة".
class _AnimatedEntrance extends StatelessWidget {
  final bool animate;
  final Widget child;

  const _AnimatedEntrance({required this.animate, required this.child});

  @override
  Widget build(BuildContext context) {
    if (!animate || MediaQuery.of(context).disableAnimations) return child;

    return TweenAnimationBuilder<double>(
      tween: Tween<double>(begin: 0, end: 1),
      duration: const Duration(milliseconds: 320),
      curve: Curves.easeOutCubic,
      child: child,
      builder: (context, t, child) => Opacity(
        opacity: t,
        child: Transform.translate(offset: Offset(0, 14 * (1 - t)), child: child),
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  final Color accentColor;
  final String personaName;
  final String? personaImagePath;
  final List<String> prompts;
  final ValueChanged<String> onPrompt;

  const _EmptyState({
    required this.accentColor,
    required this.personaName,
    required this.personaImagePath,
    required this.prompts,
    required this.onPrompt,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (personaImagePath != null)
              SizedBox(height: 120, child: Image.asset(personaImagePath!, fit: BoxFit.contain)),
            const SizedBox(height: 12),
            Text(
              'ابدأ المحادثة مع $personaName 👋',
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 6),
            const Text(
              'اسأله عن أهدافك أو مصاريفك، أو احكيله شو صار معك اليوم',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.black54, fontSize: 13),
            ),
            const SizedBox(height: 18),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              alignment: WrapAlignment.center,
              children: [
                for (final prompt in prompts)
                  ActionChip(
                    label: Text(prompt, style: const TextStyle(fontSize: 13)),
                    backgroundColor: accentColor.withValues(alpha: 0.08),
                    side: BorderSide(color: accentColor.withValues(alpha: 0.4)),
                    onPressed: () => onPrompt(prompt),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _MascotAvatar extends StatelessWidget {
  final String? path;

  const _MascotAvatar({required this.path});

  @override
  Widget build(BuildContext context) {
    final imagePath = path;
    if (imagePath == null) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsetsDirectional.only(end: 6),
      child: SizedBox(
        height: 36,
        width: 36,
        child: Image.asset(imagePath, fit: BoxFit.contain),
      ),
    );
  }
}

/// فقاعة "رشيد عم يكتب" بثلاث نقاط متحركة.
class _TypingBubble extends StatelessWidget {
  final Color accentColor;
  final String? personaImagePath;

  const _TypingBubble({required this.accentColor, required this.personaImagePath});

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: AlignmentDirectional.centerStart,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          _MascotAvatar(path: personaImagePath),
          Container(
            margin: const EdgeInsets.symmetric(vertical: 6),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            decoration: BoxDecoration(
              color: Colors.white,
              border: Border.all(color: Colors.grey.shade200),
              borderRadius: const BorderRadiusDirectional.only(
                topStart: Radius.circular(16),
                topEnd: Radius.circular(16),
                bottomStart: Radius.circular(4),
                bottomEnd: Radius.circular(16),
              ),
            ),
            child: _TypingDots(color: accentColor),
          ),
        ],
      ),
    );
  }
}

class _TypingDots extends StatefulWidget {
  final Color color;

  const _TypingDots({required this.color});

  @override
  State<_TypingDots> createState() => _TypingDotsState();
}

class _TypingDotsState extends State<_TypingDots> with SingleTickerProviderStateMixin {
  late final AnimationController _controller =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 1200));
  bool _started = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_started) return;
    _started = true;
    if (!MediaQuery.of(context).disableAnimations) _controller.repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        return Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (int i = 0; i < 3; i++)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 3),
                child: _dot(i),
              ),
          ],
        );
      },
    );
  }

  Widget _dot(int index) {
    // كل نقطة بتتأخر شوي عن اللي قبلها، فبتطلع موجة
    final t = (_controller.value - index * 0.18) % 1.0;
    final bump = math.sin(math.pi * t);
    return Transform.translate(
      offset: Offset(0, -5 * bump),
      child: Container(
        width: 8,
        height: 8,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: widget.color.withValues(alpha: 0.4 + 0.6 * bump),
        ),
      ),
    );
  }
}

class _ChatBubble extends StatelessWidget {
  final ChatMessage message;
  final Color accentColor;
  final String? personaImagePath;
  final bool isSpeaking;
  final VoidCallback? onToggleSpeak;

  const _ChatBubble({
    required this.message,
    required this.accentColor,
    required this.personaImagePath,
    this.isSpeaking = false,
    this.onToggleSpeak,
  });

  Future<void> _copy(BuildContext context) async {
    await Clipboard.setData(ClipboardData(text: message.text));
    HapticFeedback.selectionClick();
    if (!context.mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    messenger.hideCurrentSnackBar();
    messenger.showSnackBar(
      const SnackBar(content: Text('تم نسخ الرسالة'), duration: Duration(milliseconds: 1200)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final isUser = message.isFromUser;

    // الزاوية الصغيرة ("ذيل" الفقاعة) بجهة المرسل
    final borderRadius = BorderRadiusDirectional.only(
      topStart: const Radius.circular(16),
      topEnd: const Radius.circular(16),
      bottomStart: Radius.circular(isUser ? 16 : 4),
      bottomEnd: Radius.circular(isUser ? 4 : 16),
    );

    final bubble = GestureDetector(
      onLongPress: () => _copy(context),
      child: Container(
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.7),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        margin: const EdgeInsets.symmetric(vertical: 6),
        decoration: BoxDecoration(
          color: isUser ? accentColor : Colors.white,
          borderRadius: borderRadius,
          border: isUser ? null : Border.all(color: Colors.grey.shade200),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (message.isNudge)
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Text('💬 رشيد بادر بالحديث',
                    style: TextStyle(fontSize: 10, color: isUser ? Colors.white70 : accentColor)),
              ),
            Text(
              message.text,
              style: TextStyle(color: isUser ? Colors.white : Colors.black87, fontSize: 14),
            ),
            if (onToggleSpeak != null)
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: InkWell(
                  onTap: onToggleSpeak,
                  borderRadius: BorderRadius.circular(12),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 2),
                    child: Icon(
                      isSpeaking ? Icons.stop_circle_outlined : Icons.volume_up_outlined,
                      size: 18,
                      color: isSpeaking ? accentColor : Colors.black38,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );

    if (isUser) {
      return Align(alignment: AlignmentDirectional.centerEnd, child: bubble);
    }

    // رسائل رشيد: صورة الشخصية جنب الفقاعة
    return Align(
      alignment: AlignmentDirectional.centerStart,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          _MascotAvatar(path: personaImagePath),
          Flexible(child: bubble),
        ],
      ),
    );
  }
}
