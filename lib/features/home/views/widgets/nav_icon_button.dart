import 'package:flutter/material.dart';
import 'package:hugeicons/hugeicons.dart';

class NavIconButton extends StatelessWidget {
  final dynamic icon;
  final int index;
  final ValueChanged<int> onTabSelected;

  const NavIconButton({
    super.key,
    required this.icon,
    required this.index,
    required this.onTabSelected,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => onTabSelected(index),
      behavior: HitTestBehavior.opaque,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        child: HugeIcon(
          icon: icon,
          color: const Color(0xFF101828),
          size: 25,
        ),
      ),
    );
  }
}
