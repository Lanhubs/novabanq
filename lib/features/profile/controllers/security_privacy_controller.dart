import 'package:get/get.dart';
import 'package:novabanq/app/routes/app_routes.dart';
import 'package:novabanq/core/utils/helpers.dart';

class SecurityPrivacyController extends GetxController {
  final isBiometricEnabled = true.obs;
  final transactionPinStatus = 'Required for instant funding'.obs;
  final accountPasswordStatus = 'Updated 20 days ago'.obs;
  final authMethodStatus = 'Updated'.obs;

  void toggleBiometrics(bool value) {
    isBiometricEnabled.value = value;
    SnackBarHelper.showSuccess(
      message: value ? 'Biometric login enabled' : 'Biometric login disabled',
      title: 'Biometric Login',
      position: SnackPosition.BOTTOM,
      duration: const Duration(seconds: 2),
    );
  }

  void onChangeTransactionPin() {
    Get.toNamed(AppRoutes.transactionPin);
  }

  void onChangePassword() {
    SnackBarHelper.showInfo(
      message: 'Password reset link sent to your registered email address.',
      title: 'Account Password',
      position: SnackPosition.BOTTOM,
      duration: const Duration(seconds: 2),
    );
  }

  void onAuthMethodTap() {
    SnackBarHelper.showSuccess(
      message: 'Two-factor authentication is active and up to date.',
      title: 'SMS & Whatsapp Authentication',
      position: SnackPosition.BOTTOM,
      duration: const Duration(seconds: 2),
    );
      
  }
}
