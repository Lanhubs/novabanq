import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/core/widgets/custom_numeric_keypad.dart';
import 'package:novabanq/features/auth/views/widgets/auth_cta_button.dart';
import 'package:novabanq/features/auth/views/widgets/pin_code_display.dart';

class CreatePinStepView extends StatelessWidget {
  final String pin;
  final ValueChanged<String> onKeyPress;
  final VoidCallback onBackspace;
  final VoidCallback? onClear;
  final VoidCallback onContinue;
  final double horizontalPadding;

  const CreatePinStepView({
    super.key,
    required this.pin,
    required this.onKeyPress,
    required this.onBackspace,
    this.onClear,
    required this.onContinue,
    this.horizontalPadding = 20.0,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Form Content
        Expanded(
          child: SingleChildScrollView(
            physics: const BouncingScrollPhysics(),
            padding: EdgeInsets.symmetric(horizontal: horizontalPadding),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 16),

                // Title matching design
                Text(
                  "Create your\naccount pin",
                  style: GoogleFonts.outfit(
                    fontSize: 32,
                    fontWeight: FontWeight.w800,
                    color: const Color(0xFF111111),
                    height: 1.15,
                    letterSpacing: -0.6,
                  ),
                ),

                const SizedBox(height: 10),

                // Subtitle requested by user
                Text(
                  "You will use this pin to confirm your transaction moving forward",
                  style: GoogleFonts.outfit(
                    fontSize: 14,
                    fontWeight: FontWeight.w400,
                    color: const Color(0xFF667085),
                    height: 1.45,
                  ),
                ),

                const SizedBox(height: 24),

                // 5-digit Account PIN Display Boxes
                PinCodeDisplay(pin: pin, length: 5, obscure: false),

                const SizedBox(height: 24),

                // Continue Button
                AuthCtaButton(onPressed: onContinue, text: "Continue"),

                const SizedBox(height: 16),
              ],
            ),
          ),
        ),

        // Pinned Keypad Bottom Sheet (touches bottom edge)
        CustomNumericKeypad(
          onKeyPress: onKeyPress,
          onBackspace: onBackspace,
          onClear: onClear,
        ),
      ],
    );
  }
}
