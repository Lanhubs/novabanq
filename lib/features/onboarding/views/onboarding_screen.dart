import 'package:flutter/material.dart';
import 'package:get/get.dart';
import '../controllers/onboarding_controller.dart';
import 'widgets/onboarding_cta_button.dart';
import 'widgets/onboarding_illustration.dart';
import 'widgets/onboarding_page_indicator.dart';
import 'widgets/onboarding_text_content.dart';
import 'widgets/onboarding_top_bar.dart';

class OnboardingScreen extends GetView<OnboardingController> {
  const OnboardingScreen({super.key});

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
                final horizontalPadding = (constraints.maxWidth * 0.06).clamp(18.0, 26.0);
                final bottomPadding = (constraints.maxHeight * 0.025).clamp(12.0, 24.0);

                return Column(
                  children: [
                    // 1. Top Bar with Skip action
                    Padding(
                      padding: EdgeInsets.symmetric(
                        horizontal: horizontalPadding,
                        vertical: 4,
                      ),
                      child: OnboardingTopBar(
                        onSkip: controller.skipOnboarding,
                      ),
                    ),

                    // 2. Animated PageView for slides
                    Expanded(
                      child: PageView.builder(
                        controller: controller.pageController,
                        itemCount: controller.details.length,
                        onPageChanged: controller.changeActiveIndex,
                        itemBuilder: (context, index) {
                          final detail = controller.details[index];

                          return Padding(
                            padding: EdgeInsets.symmetric(
                              horizontal: horizontalPadding,
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                // Illustration with responsive flexible height
                                Expanded(
                                  child: Center(
                                    child: OnboardingIllustration(
                                      imagePath: detail.imagePath,
                                      maxHeight: constraints.maxHeight * 0.40,
                                    ),
                                  ),
                                ),

                                const SizedBox(height: 16),

                                // Left-aligned Animated Indicator
                                Obx(
                                  () => OnboardingPageIndicator(
                                    count: controller.details.length,
                                    activeIndex: controller.activeIndex.value,
                                  ),
                                ),

                                const SizedBox(height: 16),

                                // Title and Description
                                OnboardingTextContent(
                                  title: detail.title,
                                  description: detail.description,
                                ),

                                const SizedBox(height: 24),
                              ],
                            ),
                          );
                        },
                      ),
                    ),

                    // 3. Bottom CTA Capsule Button
                    Padding(
                      padding: EdgeInsets.fromLTRB(
                        horizontalPadding,
                        0,
                        horizontalPadding,
                        bottomPadding,
                      ),
                      child: Obx(
                        () => OnboardingCtaButton(
                          onPressed: controller.nextSlide,
                          text: controller.activeIndex.value ==
                                  0
                              ? 'Show me the way'
                              : controller.activeIndex.value == 2
                                  ? 'Create account'
                                  : 'Continue',
                        ),
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
