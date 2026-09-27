import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:hugeicons/hugeicons.dart';

class BottomNavTabItem extends StatelessWidget {
  final dynamic icon;
  final String label;
  final int index;
  final bool isSelected;
  final ValueChanged<int> onTabSelected;

  const BottomNavTabItem({
    super.key,
    required this.icon,
    required this.label,
    required this.index,
    required this.isSelected,
    required this.onTabSelected,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => onTabSelected(index),
      behavior: HitTestBehavior.opaque,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: isSelected
            ? const EdgeInsets.symmetric(horizontal: 18, vertical: 10)
            : const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: isSelected ? const Color(0xFF9DE7B0) : Colors.transparent,
          borderRadius: BorderRadius.circular(30),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            HugeIcon(
              icon: icon,
              color: isSelected
                  ? const Color(0xFF065F46)
                  : const Color(0xFF101828),
              size: isSelected ? 24 : 25,
            ),
            if (isSelected) ...[
              const SizedBox(width: 7),
              Text(
                label,
                style: GoogleFonts.outfit(
                  fontSize: 15.5,
                  fontWeight: FontWeight.w700,
                  color: const Color(0xFF065F46),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
