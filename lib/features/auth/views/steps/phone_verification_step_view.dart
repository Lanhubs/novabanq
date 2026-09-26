import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/core/widgets/custom_numeric_keypad.dart';
import 'package:novabanq/features/auth/views/widgets/auth_cta_button.dart';
import 'package:novabanq/features/auth/views/widgets/pin_code_display.dart';

class PhoneVerificationStepView extends StatelessWidget {
  final String pin;
  final String maskedPhone;
  final ValueChanged<String> onKeyPress;
  final VoidCallback onBackspace;
  final VoidCallback? onClear;
  final VoidCallback onResend;
  final int resendSeconds;
  final VoidCallback onContinue;
  final double horizontalPadding;

  const PhoneVerificationStepView({
    super.key,
    required this.pin,
    required this.maskedPhone,
    required this.onKeyPress,
    required this.onBackspace,
    this.onClear,
    required this.onResend,
    this.resendSeconds = 0,
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
                  "Verify your\nEmail Address",
                  style: GoogleFonts.outfit(
                    fontSize: 32,
                    fontWeight: FontWeight.w800,
                    color: const Color(0xFF111111),
                    height: 1.15,
                    letterSpacing: -0.6,
                  ),
                ),

                const SizedBox(height: 10),

                // Subtitle with masked phone number
                Text(
                  "6 digit code has been sent to $maskedPhone",
                  style: GoogleFonts.outfit(
                    fontSize: 14,
                    fontWeight: FontWeight.w400,
                    color: const Color(0xFF667085),
                    height: 1.4,
                  ),
                ),

                const SizedBox(height: 20),

                // 5-digit PIN input display boxes
                PinCodeDisplay(pin: pin, length: 6),

                const SizedBox(height: 20),

                // Continue Button
                AuthCtaButton(onPressed: onContinue, text: "Continue"),

                const SizedBox(height: 16),

                // Resend text action
                Center(
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        "Didn't receive the code? ",
                        style: GoogleFonts.outfit(
                          fontSize: 13.5,
                          fontWeight: FontWeight.w400,
                          color: const Color(0xFF667085),
                        ),
                      ),
                      InkWell(
                        onTap: resendSeconds == 0 ? onResend : null,
                        child: Text(
                          resendSeconds == 0
                              ? "Resend"
                              : "Resend in ${resendSeconds}s",
                          style: GoogleFonts.outfit(
                            fontSize: 13.5,
                            fontWeight: FontWeight.w700,
                            color: const Color(0xFF101828),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),

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
