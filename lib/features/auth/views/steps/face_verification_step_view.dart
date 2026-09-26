import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/features/auth/views/widgets/auth_cta_button.dart';

class FaceVerificationStepView extends StatelessWidget {
  final VoidCallback onTakeSelfie;

  const FaceVerificationStepView({
    super.key,
    required this.onTakeSelfie,
  });

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        return SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          child: ConstrainedBox(
            constraints: BoxConstraints(
              minHeight: constraints.maxHeight,
            ),
            child: IntrinsicHeight(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Spacer(flex: 5),

                  // Title matching design
                  Text(
                    "Take a face\nverification",
                    style: GoogleFonts.outfit(
                      fontSize: 32,
                      fontWeight: FontWeight.w700,
                      color: const Color(0xFF101828),
                      height: 1.18,
                      letterSpacing: -0.6,
                    ),
                  ),

                  const SizedBox(height: 10),

                  // Subtitle matching design
                  Text(
                    "We will use your selfie to finalize your\nverification",
                    style: GoogleFonts.outfit(
                      fontSize: 14,
                      fontWeight: FontWeight.w400,
                      color: const Color(0xFF667085),
                      height: 1.45,
                    ),
                  ),

                  const SizedBox(height: 28),

                  // Take selfie CTA Button
                  AuthCtaButton(
                    onPressed: onTakeSelfie,
                    text: "Take selfie",
                  ),

                  const Spacer(flex: 4),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}
