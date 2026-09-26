import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:hugeicons/hugeicons.dart';
import 'nav_icon_button.dart';

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
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
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
          // 1. Home Tab (Active)
          GestureDetector(
            onTap: () => onTabSelected(0),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
              decoration: BoxDecoration(
                color: currentIndex == 0
                    ? const Color(0xFF9DE7B0)
                    : Colors.transparent,
                borderRadius: BorderRadius.circular(30),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const HugeIcon(
                    icon: HugeIcons.strokeRoundedHome01,
                    color: Color(0xFF065F46),
                    size: 24,
                  ),
                  if (currentIndex == 0) ...[
                    const SizedBox(width: 7),
                    Text(
                      'Home',
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
          ),

          const SizedBox(width: 8),

          // 2. Cards Tab
          NavIconButton(
            icon: HugeIcons.strokeRoundedCreditCard,
            index: 1,
            onTabSelected: onTabSelected,
          ),

          const SizedBox(width: 6),

          // 3. Exchange / Transfer Tab
          NavIconButton(
            icon: HugeIcons.strokeRoundedExchange01,
            index: 2,
            onTabSelected: onTabSelected,
          ),

          const SizedBox(width: 6),

          // 4. Profile Tab
          NavIconButton(
            icon: HugeIcons.strokeRoundedUser,
            index: 3,
            onTabSelected: onTabSelected,
          ),
        ],
      ),
    );
  }
}
