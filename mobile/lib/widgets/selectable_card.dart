import 'package:flutter/material.dart';



class SelectableCard extends StatelessWidget {
  final bool isSelected;
  final VoidCallback onTap;
  final Widget child;
  final Color selectedColor;

  const SelectableCard({
    super.key,
    required this.isSelected,
    required this.onTap,
    required this.child,
    this.selectedColor = Colors.black87,
  });

  @override
  Widget build(BuildContext context) {
    // قارئ الشاشة لازم يعرف إنه زر وإنه مختار (مش بس حدود ملونة)
    return Semantics(
      button: true,
      selected: isSelected,
      child: InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: isSelected ? selectedColor : Colors.grey.shade300,
            width: isSelected ? 2 : 1,
          ),
        ),
        child: child,
      ),
    ),
    );
  }
}
