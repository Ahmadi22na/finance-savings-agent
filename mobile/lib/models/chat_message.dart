


class ChatMessage {
  final String text;
  final bool isFromUser;
  final bool isNudge;

  ChatMessage({required this.text, required this.isFromUser, this.isNudge = false});
}
