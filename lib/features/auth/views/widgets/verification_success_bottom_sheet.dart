import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Modal bottom sheet displaying "Verification successful" matching the screenshot
class VerificationSuccessBottomSheet extends StatelessWidget {
  const VerificationSuccessBottomSheet({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 48),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          // Green rounded rectangle check badge
          Container(
            width: 72,
            height: 72,
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(18),
              border: Border.all(
                color: const Color(0xFF22C55E), // Vibrant green border
                width: 2.5,
              ),
            ),
            child: const Center(
              child: Icon(
                Icons.check_rounded,
                size: 42,
                color: Color(0xFF22C55E),
              ),
            ),
          ),

          const SizedBox(height: 24),

          // Title
          Text(
            "Verification successful",
            style: GoogleFonts.outfit(
              fontSize: 20,
              fontWeight: FontWeight.w700,
              color: const Color(0xFF101828),
            ),
          ),

          const SizedBox(height: 8),

          // Subtitle
          Text(
            "Your number has been successfully verified",
            style: GoogleFonts.outfit(
              fontSize: 14,
              fontWeight: FontWeight.w400,
              color: const Color(0xFF667085),
            ),
            textAlign: TextAlign.center,
          ),

          const SizedBox(height: 24),
        ],
      ),
    );
  }
}
