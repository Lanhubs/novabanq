import "package:flutter/widgets.dart";
import "package:get/get.dart";
import "package:novabanq/app/routes/app_routes.dart";
import "package:novabanq/features/auth/data/data/onboarding_detail.dart";

class OnboardingController extends GetxController {
  final PageController pageController = PageController();
  final activeIndex = 0.obs;

  final List<OnboardingDetail> details = const [
    OnboardingDetail(
      title: "Africa pays Africa\nFinally",
      description:
          "Receive from Ghana, Kenya, Senegal. No detour through London. No stop in New York",
      imagePath: "assets/images/onboarding1.png",
    ),
    OnboardingDetail(
      title: "Direct rates, Zero Detours",
      description:
          "NGN to GHS direct. No USD routing, no European bank, no hidden fees. Live rates every 30 secs",
      imagePath: "assets/images/onboarding2.png",
    ),
    OnboardingDetail(
      title: "One @tag. Every African payment",
      description:
          "Share your @yourname.ng. They pay from MTN MoMo, M-Pesa, Orange moneyor any bank and you receive it",
      imagePath: "assets/images/onboarding3.png",
    ),
  ];

  void changeActiveIndex(int index) {
    activeIndex.value = index;
  }

  void nextSlide() {
    if (activeIndex.value < details.length - 1) {
      pageController.nextPage(
        duration: const Duration(milliseconds: 450),
        curve: Curves.easeInOutCubic,
      );
    } else {
      skipOnboarding();
    }
  }

  void skipOnboarding() {
    Get.offAndToNamed(AppRoutes.auth);
  }

  @override
  void onClose() {
    pageController.dispose();
    super.onClose();
  }
}
