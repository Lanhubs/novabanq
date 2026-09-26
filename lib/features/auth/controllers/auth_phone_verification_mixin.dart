import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:novabanq/features/auth/views/widgets/verification_success_bottom_sheet.dart';

mixin AuthPhoneVerificationMixin on GetxController {
  // Bracket 3, Step 4: Phone Number & Custom Keypad
  final phoneNumber = ''.obs;

  void appendPhoneNumberDigit(String digit) {
    if (phoneNumber.value.length < 15) {
      phoneNumber.value += digit;
    }
  }

  void deletePhoneNumberDigit() {
    if (phoneNumber.value.isNotEmpty) {
      phoneNumber.value =
          phoneNumber.value.substring(0, phoneNumber.value.length - 1);
    }
  }

  void clearPhoneNumber() {
    phoneNumber.value = '';
  }

  // Bracket 3, Step 5: Phone Verification (5-digit PIN)
  final verificationPin = ''.obs;

  void appendVerificationDigit(String digit) {
    if (verificationPin.value.length < 5) {
      verificationPin.value += digit;
    }
  }

  void deleteVerificationDigit() {
    if (verificationPin.value.isNotEmpty) {
      verificationPin.value =
          verificationPin.value.substring(0, verificationPin.value.length - 1);
    }
  }

  void clearVerificationPin() {
    verificationPin.value = '';
  }

  void resendVerificationCode() {
    clearVerificationPin();
    Get.snackbar(
      'Code Sent',
      'A new 5-digit verification code has been sent.',
      snackPosition: SnackPosition.BOTTOM,
      backgroundColor: const Color(0xFF005100),
      colorText: Colors.white,
      duration: const Duration(seconds: 2),
    );
  }

  String get maskedPhoneNumber {
    final raw = phoneNumber.value;
    if (raw.length >= 4) {
      final prefix = raw.substring(0, (raw.length > 3 ? 3 : 2));
      final suffix = raw.substring(raw.length - 2);
      return '$prefix***$suffix';
    }
    return '090***24';
  }

  /// Verification status modal popup, followed by advancing to BVN
  Future<void> confirmPhoneVerification({required VoidCallback onDone}) async {
    Get.bottomSheet(
      const VerificationSuccessBottomSheet(),
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      barrierColor: Colors.black.withValues(alpha: 0.5),
    );

    // Wait 1.6 seconds to let user see success confirmation, then advance
    await Future.delayed(const Duration(milliseconds: 1600));
    if (Get.isBottomSheetOpen ?? false) {
      Get.back();
    }
    onDone();
  }
}
