import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Forest-green capsule button matching the existing color model
class AuthCtaButton extends StatelessWidget {
  final VoidCallback onPressed;
  final String text;

  const AuthCtaButton({
    super.key,
    required this.onPressed,
    this.text = 'Continue',
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 420),
        child: SizedBox(
          width: double.infinity,
          height: 59,
          child: ElevatedButton(
            onPressed: onPressed,
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF005100),
              foregroundColor: Colors.white,
              elevation: 0,
              shape: const StadiumBorder(),
              padding: const EdgeInsets.symmetric(horizontal: 24),
            ),
            child: Text(
              text,
              style: GoogleFonts.outfit(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                letterSpacing: -0.2,
                color: Colors.white,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
