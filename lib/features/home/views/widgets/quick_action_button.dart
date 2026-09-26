import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:hugeicons/hugeicons.dart';

class QuickActionButton extends StatelessWidget {
  final dynamic icon;
  final String label;
  final VoidCallback onTap;

  const QuickActionButton({
    super.key,
    required this.icon,
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(35),
          child: Container(
            width: 65,
            height: 65,
            decoration: const BoxDecoration(
              color: Color(0xFFF2F4F7),
              shape: BoxShape.circle,
            ),
            child: Center(
              child: HugeIcon(
                icon: icon,
                color: const Color(0xFF101828),
                size: 28,
              ),
            ),
          ),
        ),
        const SizedBox(height: 9),
        Text(
          label,
          style: GoogleFonts.outfit(
            fontSize: 13,
            fontWeight: FontWeight.w600,
            color: const Color(0xFF344054),
          ),
        ),
      ],
    );
  }
}
