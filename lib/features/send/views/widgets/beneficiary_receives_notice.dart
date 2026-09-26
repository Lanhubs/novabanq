import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class BeneficiaryReceivesNotice extends StatelessWidget {
  final String text;

  const BeneficiaryReceivesNotice({
    super.key,
    required this.text,
  });

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Text(
        text,
        style: GoogleFonts.outfit(
          fontSize: 12,
          fontWeight: FontWeight.w500,
          color: const Color(0xFF005100),
        ),
      ),
    );
  }
}
