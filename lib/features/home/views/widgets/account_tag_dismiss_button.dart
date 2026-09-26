import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AccountTagDismissButton extends StatelessWidget {
  final VoidCallback onDismiss;

  const AccountTagDismissButton({super.key, required this.onDismiss});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onDismiss,
      behavior: HitTestBehavior.opaque,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 20),
        child: Text(
          'Not now',
          style: GoogleFonts.outfit(
            fontSize: 15,
            fontWeight: FontWeight.w500,
            color: const Color(0xFF344054),
          ),
        ),
      ),
    );
  }
}
