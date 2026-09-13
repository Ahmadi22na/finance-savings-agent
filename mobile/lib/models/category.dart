/// يطابق app/schemas/category.py -> CategoryOut بالـ Backend.
class Category {
  final String id;
  final String name;
  final String icon;
  final bool isDefault;
  final String categoryType;

  Category({
    required this.id,
    required this.name,
    required this.icon,
    required this.isDefault,
    required this.categoryType,
  });

  factory Category.fromJson(Map<String, dynamic> json) {
    return Category(
      id: json['id'] as String,
      name: json['name'] as String,
      icon: json['icon'] as String,
      isDefault: json['is_default'] as bool,
      categoryType: json['category_type'] as String,
    );
  }
}
