import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/features/auth/views/widgets/auth_cta_button.dart';
import 'package:novabanq/features/auth/views/widgets/auth_text_field.dart';
import 'package:novabanq/features/auth/models/password_rules.dart';
import 'package:novabanq/features/auth/views/widgets/password_requirement_row.dart';

class PasswordStepView extends StatelessWidget {
  final TextEditingController passwordController;
  final TextEditingController confirmPasswordController;
  final bool isPasswordVisible;
  final bool isConfirmPasswordVisible;
  final VoidCallback onTogglePasswordVisibility;
  final VoidCallback onToggleConfirmPasswordVisibility;
  final VoidCallback onContinue;
  final TextEditingController? currentPasswordController;
  final bool isCurrentPasswordVisible;
  final VoidCallback? onToggleCurrentPasswordVisibility;
  final bool isSubmitting;

  const PasswordStepView({
    super.key,
    required this.passwordController,
    required this.confirmPasswordController,
    required this.isPasswordVisible,
    required this.isConfirmPasswordVisible,
    required this.onTogglePasswordVisibility,
    required this.onToggleConfirmPasswordVisibility,
    required this.onContinue,
    this.currentPasswordController,
    this.isCurrentPasswordVisible = false,
    this.onToggleCurrentPasswordVisibility,
    this.isSubmitting = false,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Title matching design
        Text(
          "Enter your account\npassword",
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
          "Enter your password to secure your account",
          style: GoogleFonts.outfit(
            fontSize: 14,
            fontWeight: FontWeight.w400,
            color: const Color(0xFF667085),
          ),
        ),

        const SizedBox(height: 20),

        if (currentPasswordController != null) ...[
          AuthTextField(
            controller: currentPasswordController,
            label: 'Current password',
            hintText: 'Enter your current password',
            obscureText: !isCurrentPasswordVisible,
            suffixIcon: IconButton(
              icon: Icon(isCurrentPasswordVisible
                  ? Icons.visibility_rounded : Icons.visibility_off_rounded,
                size: 20, color: const Color(0xFF667085)),
              onPressed: onToggleCurrentPasswordVisibility,
            ),
          ),
          const SizedBox(height: 16),
        ],

        // Password Field
        AuthTextField(
          controller: passwordController,
          label: "Password",
          hintText: "Enter your password here",
          obscureText: !isPasswordVisible,
          suffixIcon: IconButton(
            icon: Icon(
              isPasswordVisible
                  ? Icons.visibility_rounded
                  : Icons.visibility_off_rounded,
              size: 20,
              color: const Color(0xFF667085),
            ),
            onPressed: onTogglePasswordVisibility,
          ),
        ),

        const SizedBox(height: 16),

        // Confirm Password Field
        AuthTextField(
          controller: confirmPasswordController,
          label: "Confirm password",
          hintText: "Confirm your password",
          obscureText: !isConfirmPasswordVisible,
          suffixIcon: IconButton(
            icon: Icon(
              isConfirmPasswordVisible
                  ? Icons.visibility_rounded
                  : Icons.visibility_off_rounded,
              size: 20,
              color: const Color(0xFF667085),
            ),
            onPressed: onToggleConfirmPasswordVisibility,
          ),
        ),

        const SizedBox(height: 14),

        // Password Requirements list matching the screenshot
        ValueListenableBuilder<TextEditingValue>(
          valueListenable: passwordController,
          builder: (context, value, _) => Column(
            children: [
              PasswordRequirementRow(
                text: 'Password should contain 8-10 characters',
                isMet: PasswordRules.hasValidLength(value.text),
              ),
              const SizedBox(height: 8),
              PasswordRequirementRow(
                text: 'Password should contain at least one letter',
                isMet: PasswordRules.hasLetter(value.text),
              ),
              const SizedBox(height: 8),
              PasswordRequirementRow(
                text: 'Password should contain at least one number',
                isMet: PasswordRules.hasNumber(value.text),
              ),
            ],
          ),
        ),

        const SizedBox(height: 24),

        // Continue Button
        AuthCtaButton(
          onPressed: isSubmitting ? () {} : onContinue,
          text: isSubmitting ? 'Saving...' : 'Continue',
        ),
      ],
    );
  }
}
