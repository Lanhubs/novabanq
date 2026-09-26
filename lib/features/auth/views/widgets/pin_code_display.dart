import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Reusable PIN / OTP code display boxes matching the design
class PinCodeDisplay extends StatelessWidget {
  final String pin;
  final int length;
  final bool obscure;
  final double? boxWidth;
  final double? boxHeight;

  const PinCodeDisplay({
    super.key,
    required this.pin,
    this.length = 5,
    this.obscure = false,
    this.boxWidth,
    this.boxHeight,
  });

  @override
  Widget build(BuildContext context) {
    final width = boxWidth ?? (length == 4 ? 64.0 : 54.0);
    final height = boxHeight ?? 58.0;

    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: List.generate(length, (index) {
        final hasDigit = index < pin.length;
        final digit = hasDigit
            ? (obscure ? '•' : pin[index])
            : '';
        final isCurrent = index == pin.length;

        return Container(
          width: width,
          height: height,
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(
              color: isCurrent
                  ? const Color(0xFF005100)
                  : const Color(0xFFE4E7EC),
              width: isCurrent ? 1.5 : 1.2,
            ),
          ),
          alignment: Alignment.center,
          child: Text(
            digit,
            style: GoogleFonts.outfit(
              fontSize: obscure && hasDigit ? 28 : 22,
              fontWeight: FontWeight.w700,
              color: const Color(0xFF101828),
            ),
          ),
        );
      }),
    );
  }
}
