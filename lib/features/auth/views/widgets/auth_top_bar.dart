import 'package:flutter/material.dart';
import 'package:novabanq/features/onboarding/views/widgets/onboarding_page_indicator.dart';

/// Top bar with circular back button and reused step indicator
class AuthTopBar extends StatelessWidget {
  final VoidCallback onBack;
  final int totalSteps;
  final int currentStep;

  const AuthTopBar({
    super.key,
    required this.onBack,
    this.totalSteps = 4,
    this.currentStep = 0,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        // Circular back button
        Material(
          color: const Color(0xFFF2F4F7),
          shape: const CircleBorder(),
          child: InkWell(
            onTap: onBack,
            customBorder: const CircleBorder(),
            child: const SizedBox(
              width: 40,
              height: 40,
              child: Icon(
                Icons.arrow_back_rounded,
                size: 20,
                color: Color(0xFF101828),
              ),
            ),
          ),
        ),

        // Reused step indicator (active green pill + mint dots)
        OnboardingPageIndicator(
          count: totalSteps,
          activeIndex: currentStep,
          activeColor: const Color(0xFF005100),
          inactiveColor: const Color(0xFFA5D6A7),
        ),
      ],
    );
  }
}
