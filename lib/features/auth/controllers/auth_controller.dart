import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:get/get.dart';
import 'package:novabanq/app/routes/app_routes.dart';
import 'package:novabanq/core/network/api_client.dart';
import 'package:novabanq/core/network/profile_api.dart';
import 'package:novabanq/core/services/firebase_bootstrap.dart';
import 'package:novabanq/features/auth/models/country_item.dart';
import 'package:novabanq/features/auth/models/supported_countries.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:novabanq/features/home/views/widgets/create_account_tag_input_bottom_sheet.dart';

part 'auth_flow.dart';
part 'auth_tag_flow.dart';
part 'auth_otp_timer.dart';

class AuthController extends GetxController {
  final currentStep = 0.obs;
  final totalSteps = 9;
  final totalIndicatorDots = 4;
  final busy = false.obs;
  final error = ''.obs;
  final googleSignup = false.obs;
  final countries = kSupportedCountries;
  late final Rx<CountryItem> selectedCountry;
  final isCountryDropdownOpen = false.obs;
  final emailController = TextEditingController();
  final firstNameController = TextEditingController();
  final middleNameController = TextEditingController();
  final lastNameController = TextEditingController();
  final passwordController = TextEditingController();
  final confirmPasswordController = TextEditingController();
  final bvnController = TextEditingController();
  final isPasswordVisible = false.obs;
  final isConfirmPasswordVisible = false.obs;
  final isBvnConfirmed = false.obs;
  final phoneNumber = ''.obs;
  final verificationPin = ''.obs;
  final accountPin = ''.obs;
  final resendSeconds = 0.obs;
  int resendGeneration = 0;
  late final ProfileApi api;

  int get indicatorIndex => switch (currentStep.value) {
    0 || 1 => 0,
    2 || 3 => 1,
    4 || 5 => 2,
    _ => 3,
  };
  String get fullName =>
      '${firstNameController.text} ${lastNameController.text}'.trim();
  String get e164Phone {
    final local = phoneNumber.value.replaceAll(RegExp(r'\D'), '');
    final noZero = local.startsWith('0') ? local.substring(1) : local;
    return '${selectedCountry.value.dialCode}$noZero';
  }

  String get maskedPhoneNumber {
    final email = emailController.text;
    final at = email.indexOf('@');
    return at > 1 ? '${email.substring(0, 2)}***${email.substring(at)}' : email;
  }

  @override
  void onInit() {
    super.onInit();
    selectedCountry = countries.first.obs;
    if (FirebaseBootstrap.ready) api = ProfileApi(ApiClient());
  }

  void toggleCountryDropdown() => isCountryDropdownOpen.toggle();
  void selectCountry(CountryItem value) {
    selectedCountry.value = value;
    isCountryDropdownOpen.value = false;
  }

  void togglePasswordVisibility() => isPasswordVisible.toggle();
  void toggleConfirmPasswordVisibility() => isConfirmPasswordVisible.toggle();
  void toggleBvnConfirmation(bool? value) =>
      isBvnConfirmed.value = value ?? false;
  void appendPhoneNumberDigit(String digit) {
    if (phoneNumber.value.length < 15) phoneNumber.value += digit;
  }

  void deletePhoneNumberDigit() {
    if (phoneNumber.value.isNotEmpty) {
      phoneNumber.value = phoneNumber.value.substring(
        0,
        phoneNumber.value.length - 1,
      );
    }
  }

  void clearPhoneNumber() => phoneNumber.value = '';
  void appendVerificationDigit(String digit) {
    if (verificationPin.value.length < 6) verificationPin.value += digit;
  }

  void deleteVerificationDigit() {
    if (verificationPin.value.isNotEmpty) {
      verificationPin.value = verificationPin.value.substring(
        0,
        verificationPin.value.length - 1,
      );
    }
  }

  void clearVerificationPin() => verificationPin.value = '';
  void appendAccountPinDigit(String digit) {
    if (accountPin.value.length < 5) accountPin.value += digit;
  }

  void deleteAccountPinDigit() {
    if (accountPin.value.isNotEmpty) {
      accountPin.value = accountPin.value.substring(
        0,
        accountPin.value.length - 1,
      );
    }
  }

  void clearAccountPin() => accountPin.value = '';
  void previousStep() {
    if (busy.value) return;
    if (currentStep.value > 0) {
      currentStep.value--;
      error.value = '';
    } else {
      Get.back();
    }
  }

  void nextStep() => advance();
  void signInWithGoogle() => googleSignIn();
  Future<void> handlePhoneVerificationDone() => verifyEmailCode();
  void resendVerificationCode() => sendEmailCode();
  Future<void> takeSelfie() async {
    if (!isBvnConfirmed.value) {
      error.value = 'Confirm your BVN details first.';
      return;
    }
    final result = await Get.toNamed(AppRoutes.faceScan);
    if (result == true) currentStep.value = 8;
  }

  @override
  void onClose() {
    for (final item in [
      emailController,
      firstNameController,
      middleNameController,
      lastNameController,
      passwordController,
      confirmPasswordController,
      bvnController,
    ]) {
      item.dispose();
    }
    super.onClose();
  }
}
