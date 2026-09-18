/// رسالة محادثة محلية — الـ Backend حاليًا ما عنده Endpoint لجلب سجل محادثات
/// قديم (بس بيسجلهم بجدول agent_interactions لأغراض تحليلية)، فهاي الشاشة
/// بتعرض جلسة المحادثة الحالية بس، من وقت ما فتحت الشاشة.
class ChatMessage {
  final String text;
  final bool isFromUser;
  final bool isNudge; // رسالة استباقية بادر فيها رشيد، مش رد على المستخدم

  ChatMessage({required this.text, required this.isFromUser, this.isNudge = false});
}
