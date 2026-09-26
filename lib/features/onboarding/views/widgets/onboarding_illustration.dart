import 'package:flutter/material.dart';

/// Responsive illustration widget that displays the onboarding visual
/// with graceful fallback handling if asset is loading or pending.
class OnboardingIllustration extends StatelessWidget {
  final String imagePath;
  final double maxHeight;

  const OnboardingIllustration({
    super.key,
    required this.imagePath,
    this.maxHeight = 320,
  });

  @override
  Widget build(BuildContext context) {
    final screenSize = MediaQuery.sizeOf(context);
    final safeMax = maxHeight.isFinite && maxHeight > 40.0 ? maxHeight : 320.0;
    final safeMin = (safeMax * 0.4).clamp(40.0, safeMax);
    final responsiveHeight =
        (screenSize.height * 0.36).clamp(safeMin, safeMax);

    return Center(
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxHeight: responsiveHeight,
          maxWidth: screenSize.width * 0.85,
        ),
        child: AspectRatio(
          aspectRatio: 1,
          child: Image.asset(
            imagePath,
            fit: BoxFit.contain,
            errorBuilder: (context, error, stackTrace) {
              // High-fidelity fallback placeholder while user asset is being added
              return Container(
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: const Color(0xFFF2F4F7),
                  border: Border.all(
                    color: const Color(0xFFE4E7EC),
                    width: 1.5,
                  ),
                ),
                child: Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Container(
                        padding: const EdgeInsets.all(20),
                        decoration: BoxDecoration(
                          color: const Color(0xFF005100).withValues(alpha: 0.1),
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(
                          Icons.public_rounded,
                          size: 56,
                          color: Color(0xFF005100),
                        ),
                      ),
                      const SizedBox(height: 12),
                      Text(
                        imagePath.split('/').last,
                        style: const TextStyle(
                          fontSize: 13,
                          color: Color(0xFF667085),
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}
