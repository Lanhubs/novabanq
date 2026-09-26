import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class HomeTransactionsSection extends StatelessWidget {
  final VoidCallback? onSeeMoreTap;

  const HomeTransactionsSection({super.key, this.onSeeMoreTap});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // 1. Header: "Recent transactions" & "See more"
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              'Recent transactions',
              style: GoogleFonts.outfit(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: const Color(0xFF101828),
              ),
            ),
            GestureDetector(
              onTap: onSeeMoreTap,
              child: Text(
                'See more',
                style: GoogleFonts.outfit(
                  fontSize: 12.5,
                  fontWeight: FontWeight.w500,
                  color: const Color(0xFF667085),
                ),
              ),
            ),
          ],
        ),

        const SizedBox(height: 24),

        // 2. Empty State View
        Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Image.asset(
                'assets/icons/coins.png',
                width: 116,
                height: 92,
                fit: BoxFit.contain,
              ),

              const SizedBox(height: 14),

              // "No transactions yet"
              Text(
                'No transactions yet',
                style: GoogleFonts.outfit(
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                  color: const Color(0xFF101828),
                ),
              ),

              const SizedBox(height: 6),

              // Description
              Text(
                'You have not perform any transaction,\nyour transaction sessions will show here',
                style: GoogleFonts.outfit(
                  fontSize: 12,
                  fontWeight: FontWeight.w400,
                  color: const Color(0xFF667085),
                  height: 1.45,
                ),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ],
    );
  }
}
