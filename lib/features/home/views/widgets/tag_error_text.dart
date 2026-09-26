import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class TagErrorText extends StatelessWidget {
  final String message;

  const TagErrorText({super.key, required this.message});

  @override
  Widget build(BuildContext context) {
    return Text(
      message,
      style: GoogleFonts.outfit(
        fontSize: 12,
        fontWeight: FontWeight.w500,
        color: const Color(0xFFF04438),
      ),
    );
  }
}
