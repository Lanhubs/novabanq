import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:novabanq/features/onboarding/controllers/splash_screen_controller.dart';

class SplashScreen extends GetView<SplashScreenController> {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context) {
    if (!Get.isRegistered<SplashScreenController>()) {
      Get.put(SplashScreenController());
    }
    return Scaffold(
      body: Container(
        width: double.infinity,
        height: double.infinity,
        decoration: const BoxDecoration(
          gradient: RadialGradient(
            center: Alignment(-1.0, -0.75), // Anchored in top-left corner
            radius:
                0.85, // Takes ~40% of screen before transitioning to deep green
            colors: [
              Color(0xFF46D77F), // Vivid luminous mint/emerald highlight
              Color(0xFF22B863), // Vibrant green transition
              Color(0xFF0D7B37), // Medium rich forest green
              Color(0xFF024B1B), // Dark forest green
              Color(0xFF00330E), // Deep dark green base filling ~60% of screen
            ],
            stops: [0.0, 0.20, 0.45, 0.70, 1.0],
          ),
        ),
        child: Center(
          child: _SplashEntrance(
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Stylized 'N' mark behind/with Novabanq text as in the brand visual
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    Image.asset("assets/icons/novabanq.png", width: 34),
                    const Text(
                      "ovabanq",
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 34,
                        fontWeight: FontWeight.w800,
                        letterSpacing: -0.6,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _SplashEntrance extends StatelessWidget {
  const _SplashEntrance({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    if (MediaQuery.disableAnimationsOf(context)) {
      return child;
    }

    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: const Duration(milliseconds: 1100),
      curve: Curves.easeOutCubic,
      child: child,
      builder: (context, progress, child) {
        return Opacity(
          opacity: progress,
          child: Transform.translate(
            offset: Offset(0, 12 * (1 - progress)),
            child: Transform.scale(scale: 0.94 + 0.06 * progress, child: child),
          ),
        );
      },
    );
  }
}
