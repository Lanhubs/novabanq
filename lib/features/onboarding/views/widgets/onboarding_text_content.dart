import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Renders the title and subtitle/description with responsive typography using Outfit font
class OnboardingTextContent extends StatelessWidget {
  final String title;
  final String description;

  const OnboardingTextContent({
    super.key,
    required this.title,
    required this.description,
  });

  @override
  Widget build(BuildContext context) {
    final screenWidth = MediaQuery.sizeOf(context).width;
    final screenHeight = MediaQuery.sizeOf(context).height;

    // Responsive font sizing based on device dimensions
    final titleFontSize = (screenWidth * 0.075).clamp(24.0, 32.0);
    final descriptionFontSize = (screenWidth * 0.04).clamp(14.0, 16.0);
    final spacing = (screenHeight * 0.015).clamp(10.0, 16.0);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: GoogleFonts.outfit(
            fontSize: titleFontSize,
            fontWeight: FontWeight.w800,
            color: const Color(0xFF111111),
            height: 1.18,
            letterSpacing: -0.6,
          ),
        ),
        SizedBox(height: spacing),
        Text(
          description,
          style: GoogleFonts.outfit(
            fontSize: descriptionFontSize,
            fontWeight: FontWeight.w400,
            color: const Color(0xFF667085),
            height: 1.45,
            letterSpacing: -0.1,
          ),
        ),
      ],
    );
  }
}
