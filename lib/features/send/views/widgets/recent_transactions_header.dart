import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class RecentTransactionsHeader extends StatelessWidget {
  const RecentTransactionsHeader({super.key});

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Text(
        'Recent transactions',
        style: GoogleFonts.outfit(
          fontSize: 16,
          fontWeight: FontWeight.w700,
          color: const Color(0xFF101828),
        ),
      ),
    );
  }
}
