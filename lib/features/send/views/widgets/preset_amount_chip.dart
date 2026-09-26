import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class PresetAmountChip extends StatelessWidget {
  final String label;
  final VoidCallback onTap;

  const PresetAmountChip({
    super.key,
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          color: const Color(0xFFF9FAFB),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: const Color(0xFFEAECF0),
            width: 1,
          ),
        ),
        child: Text(
          label,
          style: GoogleFonts.outfit(
            fontSize: 13,
            fontWeight: FontWeight.w500,
            color: const Color(0xFF667085),
          ),
        ),
      ),
    );
  }
}
