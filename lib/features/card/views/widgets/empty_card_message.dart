import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class EmptyCardMessage extends StatelessWidget {
  const EmptyCardMessage({super.key});

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Text(
          'No card yet',
          style: GoogleFonts.outfit(
            fontSize: 17,
            fontWeight: FontWeight.w700,
            color: const Color(0xFF101828),
          ),
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 8),
        Text(
          'You currently do not have a Novabanq\ncredit card, add a new card to start',
          style: GoogleFonts.outfit(
            fontSize: 12.5,
            fontWeight: FontWeight.w400,
            color: const Color(0xFF667085),
            height: 1.4,
          ),
          textAlign: TextAlign.center,
        ),
      ],
    );
  }
}
