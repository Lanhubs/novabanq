import 'package:get/get.dart';
import 'package:novabanq/features/onboarding/controllers/splash_screen_controller.dart';

class SplashBinding extends Bindings {
  @override
  void dependencies() {
    Get.put<SplashScreenController>(SplashScreenController());
  }
}