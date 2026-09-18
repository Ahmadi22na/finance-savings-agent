import 'package:flutter/material.dart';

/// الـ Backend بيخزّن اسم الأيقونة كنص بسيط (زي "utensils", "car"...) —
/// هاي الدالة بتحوّل النص لأيقونة Flutter فعلية. لو جانا اسم ما نعرفه (تصنيف
/// جديد انضاف بقاعدة البيانات ولسا ما حدّثنا الموبايل)، نرجّع أيقونة عامة
/// (tag) بدل ما نكسر التطبيق أو نطلع Exception.
IconData iconForKey(String key) {
  switch (key) {
    case 'utensils':
      return Icons.restaurant;
    case 'car':
      return Icons.directions_car;
    case 'shopping-cart':
      return Icons.shopping_cart;
    case 'receipt':
      return Icons.receipt_long;
    case 'shopping-bag':
      return Icons.shopping_bag;
    case 'heart-pulse':
      return Icons.favorite;
    case 'clapperboard':
      return Icons.movie;
    case 'scissors':
      return Icons.content_cut;
    case 'wallet':
      return Icons.account_balance_wallet;
    case 'target':
      return Icons.flag;
    case 'tag':
    default:
      return Icons.label;
  }
}
