import 'package:get/get.dart';
import 'package:novabanq/core/utils/helpers.dart';

class TransactionPinController extends GetxController {
  final currentStep = 0.obs; // 0=current, 1=new, 2=confirm
  final currentPin = ''.obs;
  final newPin = ''.obs;
  final confirmPin = ''.obs;

  String get stepTitle {
    switch (currentStep.value) {
      case 0:
        return 'Enter your current pin';
      case 1:
        return 'Create a new 4 digit pin';
      case 2:
        return 'Confirm new 4 digit pin';
      default:
        return '';
    }
  }

  String get stepSubtitle {
    switch (currentStep.value) {
      case 0:
        return 'Enter your current 4 digit pin to change your pin';
      case 1:
        return 'Choose a  new pin different from old pin';
      case 2:
        return 'Confirm your new account pin to proceed';
      default:
        return '';
    }
  }

  bool get showForgotLink => currentStep.value == 0;

  void onPinCompleted(String pin) {
    switch (currentStep.value) {
      case 0:
        currentPin.value = pin;
        currentStep.value = 1;
        break;
      case 1:
        newPin.value = pin;
        currentStep.value = 2;
        break;
      case 2:
        confirmPin.value = pin;
        _submitPinChange();
        break;
    }
  }

  void _submitPinChange() {
    if (newPin.value != confirmPin.value) {
      confirmPin.value = '';
      currentStep.value = 2;
      SnackBarHelper.showError(
        message: 'New pin and confirmation do not match. Please try again.',
        title: 'PIN Mismatch',
        position: SnackPosition.TOP,
        duration: const Duration(seconds: 2),
      );
      return;
    }

    Get.back();
    SnackBarHelper.showSuccess(
      message: 'Your transaction pin has been changed successfully.',
      title: 'PIN Updated',
      position: SnackPosition.TOP,
      duration: const Duration(seconds: 2),
    );
  }

  void onForgotPassword() {
    SnackBarHelper.showInfo(
      message: 'A reset link has been sent to your registered email.',
      title: 'Forgot PIN',
      position: SnackPosition.TOP,
      duration: const Duration(seconds: 2),
    );
  }

  void goBack() {
    if (currentStep.value > 0) {
      currentStep.value--;
    } else {
      Get.back();
    }
  }
}
