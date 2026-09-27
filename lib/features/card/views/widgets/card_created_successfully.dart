import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:novabanq/features/auth/views/widgets/auth_cta_button.dart';
import 'package:novabanq/features/send/views/widgets/send_money_top_bar.dart';
import 'package:google_fonts/google_fonts.dart';

class CardCreatedSuccessfully extends StatelessWidget {
  const CardCreatedSuccessfully({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20.0, vertical: 12.0),
          child: Column(
            children: [
              // Top Bar with back button only
              const SendMoneyTopBar(title: ''),

              const SizedBox(height: 20),

              // Success Illustration & Heading
              Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Image.asset(
                    'assets/icons/successful-payment.png',
                    width: Get.width * 0.4,
                    fit: BoxFit.contain,
                  ),
                  const SizedBox(height: 18),
                  Text(
                    'Your virtual card is ready',
                    style: GoogleFonts.outfit(
                      fontSize: 22,
                      fontWeight: FontWeight.w700,
                      color: const Color(0xFF101828),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Your card is now ready for use',
                    textAlign: TextAlign.center,
                    style: GoogleFonts.outfit(
                      fontSize: 14,
                      fontWeight: FontWeight.w400,
                      color: const Color(0xFF667085),
                    ),
                  ),
                ],
              ),

              const Spacer(),

              // Back to home button
              AuthCtaButton(
                text: 'Go to home',
                onPressed: () {
                  Get.offAllNamed('/home');
                },
                // onPressed: controller.backToHome,
              ),

              const SizedBox(height: 12),
            ],
          ),
        ),
      ),
    );
  }
}
