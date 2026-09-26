import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/core/widgets/custom_numeric_keypad.dart';
import 'package:novabanq/features/auth/models/country_item.dart';
import 'package:novabanq/features/auth/views/widgets/auth_cta_button.dart';

class PhoneNumberStepView extends StatelessWidget {
  final CountryItem selectedCountry;
  final String phoneNumber;
  final ValueChanged<String> onKeyPress;
  final VoidCallback onBackspace;
  final VoidCallback? onClear;
  final VoidCallback onContinue;
  final double horizontalPadding;

  const PhoneNumberStepView({
    super.key,
    required this.selectedCountry,
    required this.phoneNumber,
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
                  "Enter your\nPhone Number",
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
                  "Enter your number to open your Novabanq\naccount in 2 minutes",
                  style: GoogleFonts.outfit(
                    fontSize: 14,
                    fontWeight: FontWeight.w400,
                    color: const Color(0xFF667085),
                    height: 1.45,
                  ),
                ),

                const SizedBox(height: 20),

                // Phone Input Display Box
                Container(
                  height: 56,
                  decoration: BoxDecoration(
                    color: const Color(0xD9E7E9EC), // Exact #E7E9ECD9 background
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Row(
                    children: [
                      // Flag section
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        child: selectedCountry.flagWidget,
                      ),

                      // Vertical Divider Line matching design
                      Container(
                        width: 1,
                        height: 32,
                        color: const Color(0xFFD0D5DD),
                      ),

                      const SizedBox(width: 14),

                      // Phone Number or Placeholder Text
                      Expanded(
                        child: Text(
                          phoneNumber.isEmpty ? "+00 000 0000" : phoneNumber,
                          style: GoogleFonts.outfit(
                            fontSize: 16,
                            fontWeight: phoneNumber.isEmpty
                                ? FontWeight.w500
                                : FontWeight.w600,
                            color: phoneNumber.isEmpty
                                ? const Color(0xFF344054)
                                : const Color(0xFF101828),
                            letterSpacing: 0.5,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 18),

                // Continue Button
                AuthCtaButton(
                  onPressed: onContinue,
                  text: "Continue",
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
