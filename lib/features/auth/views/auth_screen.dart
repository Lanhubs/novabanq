import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:novabanq/features/auth/controllers/auth_controller.dart';
import 'widgets/auth_step_content.dart';
import 'widgets/auth_top_bar.dart';

class AuthScreen extends GetView<AuthController> {
  const AuthScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        bottom: false,
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: LayoutBuilder(
              builder: (context, constraints) {
                final horizontalPadding = (constraints.maxWidth * 0.06).clamp(
                  18.0,
                  24.0,
                );
                final topSpacing = constraints.maxHeight * 0.12;

                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const SizedBox(height: 8),

                    // 1. Top Bar: Circular back button + 4-step indicator
                    Padding(
                      padding: EdgeInsets.symmetric(
                        horizontal: horizontalPadding,
                      ),
                      child: Obx(
                        () => AuthTopBar(
                          onBack: controller.previousStep,
                          totalSteps: controller.totalIndicatorDots,
                          currentStep: controller.indicatorIndex,
                        ),
                      ),
                    ),

                    const SizedBox(height: 8),

                    Obx(
                      () => controller.busy.value
                          ? const LinearProgressIndicator(minHeight: 2)
                          : controller.error.value.isNotEmpty
                          ? Padding(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 20,
                              ),
                              child: Text(
                                controller.error.value,
                                style: const TextStyle(color: Colors.red),
                              ),
                            )
                          : const SizedBox(height: 2),
                    ),

                    // 2. Body for active step
                    Expanded(
                      child: AuthStepContent(
                        horizontalPadding: horizontalPadding,
                        topSpacing: topSpacing,
                      ),
                    ),
                  ],
                );
              },
            ),
          ),
        ),
      ),
    );
  }
}
