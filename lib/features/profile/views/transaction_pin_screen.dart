import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:google_fonts/google_fonts.dart';
import '../controllers/transaction_pin_controller.dart';
import 'widgets/pin_input_field.dart';

class TransactionPinScreen extends StatelessWidget {
  const TransactionPinScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final controller = Get.put(TransactionPinController());

    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Top Bar with custom back handling
                  Row(
                    children: [
                      InkWell(
                        onTap: controller.goBack,
                        borderRadius: BorderRadius.circular(22),
                        child: Container(
                          width: 42,
                          height: 42,
                          decoration: const BoxDecoration(
                            color: Color(0xFFF2F4F7),
                            shape: BoxShape.circle,
                          ),
                          child: const Center(
                            child: Icon(
                              Icons.arrow_back_rounded,
                              size: 20,
                              color: Color(0xFF101828),
                            ),
                          ),
                        ),
                      ),
                      Expanded(
                        child: Center(
                          child: Text(
                            'Transaction pin',
                            style: GoogleFonts.outfit(
                              fontSize: 17,
                              fontWeight: FontWeight.w600,
                              color: const Color(0xFF101828),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 42),
                    ],
                  ),
                  const SizedBox(height: 32),

                  // Step Title
                  Obx(
                    () => Text(
                      controller.stepTitle,
                      style: GoogleFonts.outfit(
                        fontSize: 20,
                        fontWeight: FontWeight.w700,
                        color: const Color(0xFF101828),
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),

                  // Step Subtitle
                  Obx(
                    () => Text(
                      controller.stepSubtitle,
                      style: GoogleFonts.outfit(
                        fontSize: 16,
                        color: const Color(0xFF667085),
                        height: 1.5,
                      ),
                    ),
                  ),
                  const SizedBox(height: 28),

                  // PIN Input
                  Obx(
                    () => SizedBox(
                      width: double.infinity,
                      child: PinInputField(
                        key: ValueKey(controller.currentStep.value),
                        onCompleted: controller.onPinCompleted,
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),

                  // Forgot Password Link (only on step 0)
                  Obx(
                    () => controller.showForgotLink
                        ? GestureDetector(
                            onTap: controller.onForgotPassword,
                            child: Text(
                              'Forgot password?',
                              style: GoogleFonts.outfit(
                                fontSize: 14,
                                fontWeight: FontWeight.w500,
                                color: const Color(0xFF12B76A),
                              ),
                            ),
                          )
                        : const SizedBox.shrink(),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
