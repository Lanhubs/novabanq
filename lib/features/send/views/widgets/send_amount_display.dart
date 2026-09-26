import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class SendAmountDisplay extends StatelessWidget {
  final String amount;
  final VoidCallback onTap;

  const SendAmountDisplay({
    super.key,
    required this.amount,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 24.0),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.baseline,
          textBaseline: TextBaseline.alphabetic,
          children: [
            Text(
              '₦ ',
              style: GoogleFonts.outfit(
                fontSize: 40,
                fontWeight: FontWeight.w700,
                color: const Color(0xFF98A2B3),
              ),
            ),
            Text(
              amount,
              style: GoogleFonts.outfit(
                fontSize: 44,
                fontWeight: FontWeight.w700,
                color: const Color(0xFF1D2939),
                letterSpacing: -0.5,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
