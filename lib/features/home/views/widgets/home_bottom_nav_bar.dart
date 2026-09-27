import 'package:flutter/material.dart';
import 'package:hugeicons/hugeicons.dart';
import 'bottom_nav_tab_item.dart';

class HomeBottomNavBar extends StatelessWidget {
  final int currentIndex;
  final Function(int index) onTabSelected;

  const HomeBottomNavBar({
    super.key,
    required this.currentIndex,
    required this.onTabSelected,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: const Color(0xFFEEF2F6),
        borderRadius: BorderRadius.circular(40),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.07),
            blurRadius: 20,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          BottomNavTabItem(
            icon: HugeIcons.strokeRoundedHome01,
            label: 'Home',
            index: 0,
            isSelected: currentIndex == 0,
            onTabSelected: onTabSelected,
          ),
          const SizedBox(width: 4),
          BottomNavTabItem(
            icon: HugeIcons.strokeRoundedCreditCard,
            label: 'Cards',
            index: 1,
            isSelected: currentIndex == 1,
            onTabSelected: onTabSelected,
          ),
          const SizedBox(width: 4),
          BottomNavTabItem(
            icon: HugeIcons.strokeRoundedExchange01,
            label: 'Transfer',
            index: 2,
            isSelected: currentIndex == 2,
            onTabSelected: onTabSelected,
          ),
          const SizedBox(width: 4),
          BottomNavTabItem(
            icon: HugeIcons.strokeRoundedUser,
            label: 'Profile',
            index: 3,
            isSelected: currentIndex == 3,
            onTabSelected: onTabSelected,
          ),
        ],
      ),
    );
  }
}
