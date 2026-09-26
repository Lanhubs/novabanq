import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/core/widgets/google_logo.dart';
import 'package:novabanq/features/auth/views/widgets/auth_cta_button.dart';
import 'package:novabanq/features/auth/views/widgets/auth_text_field.dart';

class EmailStepView extends StatelessWidget {
  final TextEditingController controller;
  final VoidCallback onContinue;
  final VoidCallback? onGoogleSignUp;

  const EmailStepView({
    super.key,
    required this.controller,
    required this.onContinue,
    this.onGoogleSignUp,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Title matching design
        Text(
          "What's your\nemail address?",
          style: GoogleFonts.outfit(
            fontSize: 32,
            fontWeight: FontWeight.w800,
            color: const Color(0xFF111111),
            height: 1.15,
            letterSpacing: -0.6,
          ),
        ),

        const SizedBox(height: 10),

        // Subtitle matching design
        Text(
          "Enter your email address to open your\nNovabanq account in 2 minutes",
          style: GoogleFonts.outfit(
            fontSize: 14,
            fontWeight: FontWeight.w400,
            color: const Color(0xFF667085),
            height: 1.45,
          ),
        ),

        const SizedBox(height: 20),

        // Reusable Email Input Field with #E7E9ECD9 background
        AuthTextField(
          controller: controller,
          hintText: "Enter email address",
          keyboardType: TextInputType.emailAddress,
        ),

        const SizedBox(height: 20),

        // "Or continue with" divider
        Row(
          children: [
            const Expanded(
              child: Divider(color: Color(0xFFE4E7EC), thickness: 1),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: Text(
                "Or continue with",
                style: GoogleFonts.outfit(
                  fontSize: 12,
                  fontWeight: FontWeight.w400,
                  color: const Color(0xFF667085),
                ),
              ),
            ),
            const Expanded(
              child: Divider(color: Color(0xFFE4E7EC), thickness: 1),
            ),
          ],
        ),

        const SizedBox(height: 18),

        // "Sign up with google" Button
        Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: SizedBox(
              width: double.infinity,
              height: 56,
              child: OutlinedButton(
                onPressed: onGoogleSignUp ?? () {},
                style: OutlinedButton.styleFrom(
                  backgroundColor: Colors.white,
                  foregroundColor: const Color(0xFF101828),
                  side: const BorderSide(color: Color(0xFFE4E7EC), width: 1.2),
                  shape: const StadiumBorder(),
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const GoogleLogo(size: 20),
                    const SizedBox(width: 10),
                    Text(
                      "Sign up with google",
                      style: GoogleFonts.outfit(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: const Color(0xFF101828),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),

        const SizedBox(height: 16),

        // Continue Button
        AuthCtaButton(
          onPressed: onContinue,
          text: "Continue",
        ),
      ],
    );
  }
}
