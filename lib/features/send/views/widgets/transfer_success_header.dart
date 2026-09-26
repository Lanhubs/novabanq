import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class TransferSuccessHeader extends StatelessWidget {
  const TransferSuccessHeader({super.key});

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Image.asset(
          'assets/icons/successful-payment.png',
          width: 120,
          height: 120,
          fit: BoxFit.contain,
        ),
        const SizedBox(height: 18),
        Text(
          'Transfer successful',
          style: GoogleFonts.outfit(
            fontSize: 22,
            fontWeight: FontWeight.w700,
            color: const Color(0xFF101828),
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'Beneficiary has been successfully credited',
          textAlign: TextAlign.center,
          style: GoogleFonts.outfit(
            fontSize: 14,
            fontWeight: FontWeight.w400,
            color: const Color(0xFF667085),
          ),
        ),
      ],
    );
  }
}
