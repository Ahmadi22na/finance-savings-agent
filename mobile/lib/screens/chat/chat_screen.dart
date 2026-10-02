import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../core/api_client.dart';
import '../../models/chat_message.dart';
import '../../theme/app_theme.dart';

class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final _messages = <ChatMessage>[];
  final _textController = TextEditingController();
  final _scrollController = ScrollController();
  bool _isSending = false;
  bool _checkedNudge = false;
  int? _speakingIndex; // index الرسالة يلي عم تتنطق هلأ، أو null

  @override
  void initState() {
    super.initState();
    // أول ما تفتح الشاشة، منفحص إذا رشيد عنده شي يبادر فيه (Nudge) —
    // نفس فكرة /agent/nudge بالضبط، هون منستدعيها أول ما المستخدم يدخل الشات
    WidgetsBinding.instance.addPostFrameCallback((_) => _checkForNudge());
  }

  @override
  void dispose() {
    // ما نسيب صوت رشيد يضل يحكي بعد ما المستخدم طلع من شاشة الشات
    ref.read(ttsServiceProvider).stop();
    _textController.dispose();
    _scrollController.dispose();
    super.dispose();
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
      // فشل فحص الـ Nudge مش شي حرج — الشات بيضل يشتغل عادي بدونه
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

  Future<void> _send() async {
    final text = _textController.text.trim();
    if (text.isEmpty || _isSending) return;

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

    return Scaffold(
      appBar: AppBar(
        title: Text(persona?.displayName ?? 'رشيد'),
      ),
      body: Column(
        children: [
          Expanded(
            child: !_checkedNudge && _messages.isEmpty
                ? const Center(child: CircularProgressIndicator())
                : _messages.isEmpty
                    ? Center(
                        child: Padding(
                          padding: const EdgeInsets.all(24),
                          child: Text(
                            'ابدأ المحادثة مع ${persona?.displayName ?? "رشيد"} 👋',
                            style: const TextStyle(color: Colors.black54),
                          ),
                        ),
                      )
                    : ListView.builder(
                        controller: _scrollController,
                        padding: const EdgeInsets.all(16),
                        itemCount: _messages.length,
                        itemBuilder: (context, index) {
                          final message = _messages[index];
                          return _ChatBubble(
                            message: message,
                            accentColor: accentColor,
                            personaImagePath: persona?.imageAssetPath,
                            isSpeaking: _speakingIndex == index,
                            onToggleSpeak:
                                message.isFromUser ? null : () => _toggleSpeak(index, message.text),
                          );
                        },
                      ),
          ),
          if (_isSending)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 4),
              child: Text('رشيد عم يفكّر...', style: TextStyle(color: Colors.black45, fontSize: 12)),
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
                      onSubmitted: (_) => _send(),
                      decoration: const InputDecoration(
                        hintText: 'اكتب رسالتك...',
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton.filled(
                    style: IconButton.styleFrom(backgroundColor: accentColor),
                    onPressed: _isSending ? null : _send,
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
}

class _ChatBubble extends StatelessWidget {
  final ChatMessage message;
  final Color accentColor;
  final String? personaImagePath;
  final bool isSpeaking;
  final VoidCallback? onToggleSpeak; // null لرسائل المستخدم (ما بننطقها)

  const _ChatBubble({
    required this.message,
    required this.accentColor,
    required this.personaImagePath,
    this.isSpeaking = false,
    this.onToggleSpeak,
  });

  @override
  Widget build(BuildContext context) {
    final isUser = message.isFromUser;

    final bubble = Container(
      constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.7),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      margin: const EdgeInsets.symmetric(vertical: 6),
      decoration: BoxDecoration(
        color: isUser ? accentColor : Colors.white,
        borderRadius: BorderRadius.circular(16),
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
    );

    if (isUser) {
      return Align(alignment: AlignmentDirectional.centerEnd, child: bubble);
    }

    // رسائل رشيد: صورة صغيرة له جنب الفقاعة، عشان الشخصية تبان حتى بالنص
    return Align(
      alignment: AlignmentDirectional.centerStart,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          if (personaImagePath != null)
            Padding(
              padding: const EdgeInsetsDirectional.only(end: 6),
              child: SizedBox(
                height: 36, width: 36,
                child: Image.asset(personaImagePath!, fit: BoxFit.contain),
              ),
            ),
          Flexible(child: bubble),
        ],
      ),
    );
  }
}
