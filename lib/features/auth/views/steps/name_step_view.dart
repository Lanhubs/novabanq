import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/features/auth/views/widgets/auth_cta_button.dart';
import 'package:novabanq/features/auth/views/widgets/auth_text_field.dart';

class NameStepView extends StatelessWidget {
  final TextEditingController firstNameController;
  final TextEditingController middleNameController;
  final TextEditingController lastNameController;
  final VoidCallback onContinue;

  const NameStepView({
    super.key,
    required this.firstNameController,
    required this.middleNameController,
    required this.lastNameController,
    required this.onContinue,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Title matching design
        Text(
          "What is your\nname?",
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
          "Enter your name as it appears on your\ngovernment ID",
          style: GoogleFonts.outfit(
            fontSize: 14,
            fontWeight: FontWeight.w400,
            color: const Color(0xFF667085),
            height: 1.4,
          ),
        ),

        const SizedBox(height: 20),

        // First Name Input Field
        AuthTextField(
          controller: firstNameController,
          label: "First name",
          hintText: "Enter your first name",
          keyboardType: TextInputType.name,
        ),

        const SizedBox(height: 16),

        // Middle Name Input Field
        AuthTextField(
          controller: middleNameController,
          label: "Middle name",
          hintText: "Enter your middle name",
          keyboardType: TextInputType.name,
        ),

        const SizedBox(height: 16),

        // Last Name Input Field
        AuthTextField(
          controller: lastNameController,
          label: "Last name",
          hintText: "Enter your last name",
          keyboardType: TextInputType.name,
        ),

        const SizedBox(height: 24),

        // Continue CTA Button
        AuthCtaButton(
          onPressed: onContinue,
          text: "Continue",
        ),
      ],
    );
  }
}
