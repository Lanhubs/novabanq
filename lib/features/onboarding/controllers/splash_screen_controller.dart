import 'package:get/get.dart';
import 'package:novabanq/app/routes/app_routes.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:novabanq/core/network/api_client.dart';
import 'package:novabanq/core/network/profile_api.dart';
import 'package:novabanq/core/services/firebase_bootstrap.dart';

class SplashScreenController extends GetxController {
  bool _hasNavigated = false;

  @override
  void onInit() {
    super.onInit();
    checkInitialRoute();
  }

  Future<void> checkInitialRoute() async {
    // Wait for splash screen display (2.5 seconds)
    await Future.delayed(const Duration(milliseconds: 2500));

    if (_hasNavigated) return;
    _hasNavigated = true;
    if (FirebaseBootstrap.ready && FirebaseAuth.instance.currentUser != null) {
      try {
        await ProfileApi(ApiClient()).profile();
        Get.offAllNamed(AppRoutes.home);
        return;
      } on ApiFailure {
        /* No completed profile: resume sign-up. */
      }
    }
    Get.offAllNamed(AppRoutes.onboarding);
  }
}
