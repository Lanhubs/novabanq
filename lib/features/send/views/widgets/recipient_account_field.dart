import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class RecipientAccountField extends StatelessWidget {
  final TextEditingController controller;

  const RecipientAccountField({super.key, required this.controller});

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      keyboardType: TextInputType.number,
      style: GoogleFonts.outfit(
        fontSize: 15,
        fontWeight: FontWeight.w500,
        color: const Color(0xFF101828),
      ),
      decoration: InputDecoration(
        hintText: 'Enter account number',
        hintStyle: GoogleFonts.outfit(
          fontSize: 14.5,
          color: const Color(0xFF98A2B3),
        ),
        border: InputBorder.none,
        isDense: true,
        contentPadding: const EdgeInsets.symmetric(vertical: 12),
      ),
    );
  }
}
