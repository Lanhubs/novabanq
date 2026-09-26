import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/features/auth/views/widgets/auth_cta_button.dart';
import 'package:novabanq/features/auth/views/widgets/auth_text_field.dart';

class BvnStepView extends StatelessWidget {
  final TextEditingController controller;
  final bool isConfirmed;
  final ValueChanged<bool?> onToggleConfirm;
  final VoidCallback onConfirm;

  const BvnStepView({
    super.key,
    required this.controller,
    required this.isConfirmed,
    required this.onToggleConfirm,
    required this.onConfirm,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Title matching design
        Text(
          "Enter your\nBVN",
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
          "We will use your BVN to verify your account",
          style: GoogleFonts.outfit(
            fontSize: 14,
            fontWeight: FontWeight.w400,
            color: const Color(0xFF667085),
            height: 1.4,
          ),
        ),

        const SizedBox(height: 20),

        // BVN Input Field with #E7E9ECD9 background
        AuthTextField(
          controller: controller,
          hintText: "Enter your BVN",
          keyboardType: TextInputType.number,
        ),

        const SizedBox(height: 18),

        // Confirm Button
        AuthCtaButton(
          onPressed: onConfirm,
          text: "Confirm",
        ),

        const SizedBox(height: 48),

        // Bottom Confirmation Checkbox and Disclaimer
        InkWell(
          onTap: () => onToggleConfirm(!isConfirmed),
          borderRadius: BorderRadius.circular(4),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 20,
                height: 20,
                margin: const EdgeInsets.only(top: 2),
                decoration: BoxDecoration(
                  color: isConfirmed ? const Color(0xFF005100) : Colors.white,
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(
                    color: isConfirmed
                        ? const Color(0xFF005100)
                        : const Color(0xFFD0D5DD),
                    width: 1.5,
                  ),
                ),
                child: isConfirmed
                    ? const Icon(
                        Icons.check_rounded,
                        size: 14,
                        color: Colors.white,
                      )
                    : null,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  "I confirm that the BVN is mine and can be used\nfor verification",
                  style: GoogleFonts.outfit(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w400,
                    color: const Color(0xFF667085),
                    height: 1.4,
                  ),
                ),
              ),
            ],
          ),
        ),

        const SizedBox(height: 16),
      ],
    );
  }
}
