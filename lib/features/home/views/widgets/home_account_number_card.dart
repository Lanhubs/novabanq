import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:hugeicons/hugeicons.dart';

class HomeAccountNumberCard extends StatelessWidget {
  final String currency;
  final String maskedAccountNumber;
  final VoidCallback onCopy;

  const HomeAccountNumberCard({
    super.key,
    this.currency = 'NGN',
    required this.maskedAccountNumber,
    required this.onCopy,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onCopy,
      behavior: HitTestBehavior.opaque,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            '$currency Account number: $maskedAccountNumber',
            style: GoogleFonts.outfit(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: const Color(0xFF667085),
            ),
          ),
          const SizedBox(width: 6),
          const HugeIcon(
            icon: HugeIcons.strokeRoundedCopy01,
            color: Color(0xFF667085),
            size: 17.5,
          ),
        ],
      ),
    );
  }
}
