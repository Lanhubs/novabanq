import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class SendSourceAccountCard extends StatelessWidget {
  final String title;
  final String balance;
  final VoidCallback? onChange;

  const SendSourceAccountCard({
    super.key,
    required this.title,
    required this.balance,
    this.onChange,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        // Green card icon
        Container(
          width: 36,
          height: 26,
          decoration: BoxDecoration(
            color: const Color(0xFF005100),
            borderRadius: BorderRadius.circular(5),
          ),
          padding: const EdgeInsets.all(4),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                width: 7,
                height: 5,
                decoration: BoxDecoration(
                  color: const Color(0xFF38D377),
                  borderRadius: BorderRadius.circular(1.5),
                ),
              ),
              Container(
                width: double.infinity,
                height: 2,
                color: Colors.white30,
              ),
            ],
          ),
        ),

        const SizedBox(width: 12),

        // Title and Balance
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: GoogleFonts.outfit(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: const Color(0xFF101828),
                ),
              ),
              const SizedBox(height: 2),
              RichText(
                text: TextSpan(
                  text: 'Balance:  ',
                  style: GoogleFonts.outfit(
                    fontSize: 13,
                    fontWeight: FontWeight.w400,
                    color: const Color(0xFF667085),
                  ),
                  children: [
                    TextSpan(
                      text: '₦ $balance',
                      style: GoogleFonts.outfit(
                        fontSize: 13,
                        fontWeight: FontWeight.w500,
                        color: const Color(0xFF667085),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),

        // Change button
        InkWell(
          onTap: onChange,
          borderRadius: BorderRadius.circular(16),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
            decoration: BoxDecoration(
              color: const Color(0xFFF9FAFB),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: const Color(0xFFEAECF0),
                width: 1,
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'Change',
                  style: GoogleFonts.outfit(
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                    color: const Color(0xFF344054),
                  ),
                ),
                const SizedBox(width: 6),
                const Icon(
                  Icons.arrow_forward_rounded,
                  size: 14,
                  color: Color(0xFF344054),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
