import 'package:get/get.dart';
import 'package:novabanq/app/routes/app_routes.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:novabanq/core/network/api_client.dart';
import 'package:novabanq/core/network/profile_api.dart';
import 'package:novabanq/core/services/firebase_bootstrap.dart';
import 'package:novabanq/core/services/storage_service.dart';

class SplashScreenController extends GetxController {
  bool _hasNavigated = false;
  final isFirstTimeUser = true.obs;

  @override
  void onInit() {
    super.onInit();
    
    checkInitialRoute();
  }

  

  Future<void> checkInitialRoute() async {
    // Wait for splash screen display (2.5 seconds)
    isFirstTimeUser.value = await StorageService.getIsFirstTimeUser();
    await Future.delayed(const Duration(milliseconds: 2500));

    if (_hasNavigated) return;
    _hasNavigated = true;

    // 1. If user is a first-timer, send to onboarding
    if (isFirstTimeUser.value) {
      Get.offAllNamed(AppRoutes.onboarding);
      return;
    }

    // 2. If user is NOT a first-timer, check authentication status
    final user = FirebaseAuth.instance.currentUser;

    if (FirebaseBootstrap.ready && user != null) {
      try {
        await ProfileApi(ApiClient()).profile();
        Get.offAllNamed(AppRoutes.home);
        return;
      } on ApiFailure {
        /* No completed profile: resume sign-up/onboarding */
        Get.offAllNamed(AppRoutes.onboarding);
        return;
      }
    }

    // 3. Not a first-timer and NOT logged in -> go to login
    Get.offAllNamed(AppRoutes.login);
  }
}