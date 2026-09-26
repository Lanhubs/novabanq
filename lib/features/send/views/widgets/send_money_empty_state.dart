import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class SendMoneyEmptyState extends StatelessWidget {
  const SendMoneyEmptyState({super.key});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // 1. Coins illustration from assets
          Image.asset(
            'assets/icons/coins.png',
            width: 116,
            height: 92,
            fit: BoxFit.contain,
          ),

          const SizedBox(height: 14),

          // 2. Title
          Text(
            'No transactions yet',
            style: GoogleFonts.outfit(
              fontSize: 17,
              fontWeight: FontWeight.w700,
              color: const Color(0xFF101828),
            ),
          ),

          const SizedBox(height: 6),

          // 3. Description
          Text(
            'You have not performed any transaction,\nyour transaction sessions will show here',
            style: GoogleFonts.outfit(
              fontSize: 13.5,
              fontWeight: FontWeight.w400,
              color: const Color(0xFF667085),
              height: 1.45,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}
