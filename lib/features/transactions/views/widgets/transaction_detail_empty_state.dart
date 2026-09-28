import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class TransactionDetailEmptyState extends StatelessWidget {
  const TransactionDetailEmptyState({super.key});

  @override
  Widget build(BuildContext context) => Center(
    child: Text(
      'Transaction not found',
      style: GoogleFonts.outfit(
        fontSize: 16,
        fontWeight: FontWeight.w500,
        color: const Color(0xFF667085),
      ),
    ),
  );
}
