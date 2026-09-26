import 'package:flutter/material.dart';

/// Left-aligned animated pill and dots page indicator matching the design
class OnboardingPageIndicator extends StatelessWidget {
  final int count;
  final int activeIndex;
  final Color activeColor;
  final Color inactiveColor;

  const OnboardingPageIndicator({
    super.key,
    required this.count,
    required this.activeIndex,
    this.activeColor = const Color(0xFF005100),
    this.inactiveColor = const Color(0xFFA5D6A7),
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: List.generate(count, (index) {
        final isActive = index == activeIndex;
        return AnimatedContainer(
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeInOut,
          margin: const EdgeInsets.only(right: 7),
          height: 8,
          width: isActive ? 34 : 8,
          decoration: BoxDecoration(
            color: isActive ? activeColor : inactiveColor,
            borderRadius: BorderRadius.circular(4),
          ),
        );
      }),
    );
  }
}
