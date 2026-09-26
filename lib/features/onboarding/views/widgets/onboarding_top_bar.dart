import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Top bar containing the 'Skip' navigation action styled with Outfit font
class OnboardingTopBar extends StatelessWidget {
  final VoidCallback onSkip;

  const OnboardingTopBar({
    super.key,
    required this.onSkip,
  });

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerRight,
      child: TextButton(
        onPressed: onSkip,
        style: TextButton.styleFrom(
          foregroundColor: const Color(0xFF1F2937),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          minimumSize: Size.zero,
          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
        ),
        child: Text(
          'Skip',
          style: GoogleFonts.outfit(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            letterSpacing: -0.2,
          ),
        ),
      ),
    );
  }
}
