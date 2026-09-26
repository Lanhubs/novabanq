import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/app/routes/app_routes.dart';
import 'package:novabanq/features/auth/controllers/auth_controller.dart';
import 'package:novabanq/features/auth/views/widgets/auth_cta_button.dart';
import 'package:novabanq/features/auth/views/widgets/celebration_badge.dart';
import 'package:firebase_auth/firebase_auth.dart';

class AccountSuccessScreen extends StatelessWidget {
  const AccountSuccessScreen({super.key});

  String _getUserGreeting() {
    if (Get.isRegistered<AuthController>()) {
      final authController = Get.find<AuthController>();
      final name = authController.firstNameController.text.trim();
      if (name.isNotEmpty) {
        return "Hi $name!";
      }
    }
    final name = FirebaseAuth.instance.currentUser?.displayName
        ?.split(' ')
        .first;
    return name == null || name.isEmpty ? 'Welcome!' : 'Hi $name!';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: LayoutBuilder(
              builder: (context, constraints) {
                final horizontalPadding = (constraints.maxWidth * 0.07).clamp(
                  20.0,
                  32.0,
                );

                return Padding(
                  padding: EdgeInsets.symmetric(horizontal: horizontalPadding),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.center,
                    children: [
                      const Spacer(flex: 3),

                      // 1. Festive Celebration Badge matching design
                      const CelebrationBadge(size: 114),

                      const SizedBox(height: 16),

                      // 2. Personal greeting: "Hi Danclem!"
                      Text(
                        _getUserGreeting(),
                        style: GoogleFonts.outfit(
                          fontSize: 22,
                          fontWeight: FontWeight.w700,
                          color: const Color(0xFF101828),
                          letterSpacing: -0.3,
                        ),
                        textAlign: TextAlign.center,
                      ),

                      const SizedBox(height: 24),

                      // 3. Headline: "We're glad to have you on board"
                      Text(
                        "We’re glad to have\nyou on board",
                        style: GoogleFonts.outfit(
                          fontSize: 30,
                          fontWeight: FontWeight.w800,
                          color: const Color(0xFF101828),
                          height: 1.2,
                          letterSpacing: -0.6,
                        ),
                        textAlign: TextAlign.center,
                      ),

                      const SizedBox(height: 10),

                      // 4. Subtitle: "Your step to Africa financial ease is here"
                      Text(
                        "Your step to Africa financial ease is here",
                        style: GoogleFonts.outfit(
                          fontSize: 14,
                          fontWeight: FontWeight.w400,
                          color: const Color(0xFF667085),
                        ),
                        textAlign: TextAlign.center,
                      ),

                      const Spacer(flex: 4),

                      // 5. CTA Button: "Go to home"
                      AuthCtaButton(
                        onPressed: () {
                          Get.offAllNamed(
                            AppRoutes.home,
                            arguments: {'fromSignUp': true},
                          );
                        },
                        text: "Go to home",
                      ),

                      const SizedBox(height: 24),
                    ],
                  ),
                );
              },
            ),
          ),
        ),
      ),
    );
  }
}
