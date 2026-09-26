import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class RecentTransactionAvatar extends StatelessWidget {
  final String name;
  final int index;

  const RecentTransactionAvatar({
    super.key,
    required this.name,
    this.index = 0,
  });

  @override
  Widget build(BuildContext context) {
    final avatarColors = [
      const Color(0xFFD97706),
      const Color(0xFF0284C7),
      const Color(0xFF7C3AED),
      const Color(0xFF059669),
    ];
    final color = avatarColors[index % avatarColors.length];
    final initials = name.isNotEmpty ? name.substring(0, 1).toUpperCase() : 'U';

    return Container(
      width: 46,
      height: 46,
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        shape: BoxShape.circle,
        border: Border.all(
          color: color.withValues(alpha: 0.3),
          width: 1.5,
        ),
      ),
      child: Center(
        child: Text(
          initials,
          style: GoogleFonts.outfit(
            fontSize: 18,
            fontWeight: FontWeight.w700,
            color: color,
          ),
        ),
      ),
    );
  }
}
