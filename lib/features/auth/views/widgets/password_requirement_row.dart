import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class PasswordRequirementRow extends StatelessWidget {
  const PasswordRequirementRow({super.key, required this.text,
    required this.isMet});

  final String text;
  final bool isMet;

  @override
  Widget build(BuildContext context) {
    final color = isMet ? const Color(0xFF1A9B51) : const Color(0xFF667085);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Icon(isMet ? Icons.check_circle_outline : Icons.info_outline_rounded,
          size: 16, color: color),
        const SizedBox(width: 8),
        Expanded(child: Text(text, style: GoogleFonts.outfit(
          fontSize: 12.5, fontWeight: FontWeight.w400, color: color))),
      ],
    );
  }
}
