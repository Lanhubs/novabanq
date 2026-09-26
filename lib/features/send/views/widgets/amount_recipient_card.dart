import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AmountRecipientCard extends StatelessWidget {
  final String name;
  final String accountInfo;

  const AmountRecipientCard({
    super.key,
    required this.name,
    required this.accountInfo,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        // Green circle avatar with initial
        // Solid green circle avatar with brand N
        Container(
          width: 48,
          height: 48,
          decoration: const BoxDecoration(
            color: Color(0xFF005100),
            shape: BoxShape.circle,
          ),
          child: Center(
            child: Text(
              'N',
              style: GoogleFonts.outfit(
                fontSize: 22,
                fontWeight: FontWeight.w800,
                color: const Color(0xFF38D377),
              ),
            ),
          ),
        ),

        const SizedBox(width: 14),

        // Name + Account
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                name,
                style: GoogleFonts.outfit(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  color: const Color(0xFF101828),
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 2),
              Text(
                accountInfo,
                style: GoogleFonts.outfit(
                  fontSize: 13,
                  fontWeight: FontWeight.w400,
                  color: const Color(0xFF667085),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
