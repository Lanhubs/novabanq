import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/services.dart';
import 'package:get/get.dart';
import 'package:novabanq/app/routes/app_routes.dart';
import 'package:novabanq/core/utils/helpers.dart';
import 'package:novabanq/core/network/api_client.dart';
import 'package:novabanq/core/network/profile_api.dart';
import 'package:novabanq/features/auth/controllers/auth_controller.dart';

class ProfileController extends GetxController {
  final userName = 'Toluwalase Daniel'.obs;
  final tierStatus = 'Tier 2 account'.obs;
  final appearanceSetting = 'System default (Light)'.obs;
  final languageSetting = 'English (Nigeria)'.obs;
  final isLoading = false.obs;

  final accountNumber = '89212818091'.obs;
  final accountName = 'John Tolu Kumasi'.obs;
  final dateOfBirth = 'Set date of birth'.obs;
  final emailAddress = 'dan**@gmail.com'.obs;
  final mobileNumber = '09087653291'.obs;
  final gender = 'Male'.obs;

  ProfileApi get profileApi => _profileApi ??= ProfileApi(ApiClient());
  ProfileApi? _profileApi;

  @override
  void onInit() {
    super.onInit();
    loadUserProfile();
  }

  Future<void> loadUserProfile() async {
    try {
      if (Get.isRegistered<AuthController>()) {
        final auth = Get.find<AuthController>();
        final name = auth.fullName.trim();
        if (name.isNotEmpty) {
          userName.value = name;
          accountName.value = name;
        }
        if (auth.emailController.text.trim().isNotEmpty) {
          _maskEmail(auth.emailController.text.trim());
        }
      }

      final profileData = await profileApi.profile().catchError(
        (_) => <String, dynamic>{},
      );
      final fName = profileData['first_name']?.toString() ?? '';
      final lName = profileData['last_name']?.toString() ?? '';
      if (fName.isNotEmpty || lName.isNotEmpty) {
        final full = '$fName $lName'.trim();
        userName.value = full;
        accountName.value = full;
      }
      if (profileData['account_number'] != null &&
          profileData['account_number'].toString().isNotEmpty) {
        accountNumber.value = profileData['account_number'].toString();
      }
      if (profileData['email'] != null &&
          profileData['email'].toString().isNotEmpty) {
        _maskEmail(profileData['email'].toString());
      }
      if (profileData['phone'] != null &&
          profileData['phone'].toString().isNotEmpty) {
        mobileNumber.value = profileData['phone'].toString();
      }
    } catch (_) {}
  }

  void _maskEmail(String email) {
    if (email.contains('@')) {
      final parts = email.split('@');
      final prefix = parts[0].length > 3 ? parts[0].substring(0, 3) : parts[0];
      emailAddress.value = '$prefix**@${parts[1]}';
    } else {
      emailAddress.value = email;
    }
  }

  void onPersonalInformationTap() {
    Get.toNamed(AppRoutes.personalInformation);
  }

  void copyAccountNumber() {
    Clipboard.setData(ClipboardData(text: accountNumber.value));
    _showSnackbar(
      'Copied',
      'Account number copied to clipboard',
      isSuccess: true,
    );
  }

  void onEditDateOfBirth() {
    _showSnackbar(
      'Date of Birth',
      'Contact support to update verified date of birth.',
    );
  }

  void onEditEmail() {
    _showSnackbar('Email Address', 'Email verification link has been sent.');
  }

  void onChangeAvatar() {
    _showSnackbar('Profile Photo', 'Photo upload feature is coming soon.');
  }

  void onSecurityPrivacyTap() {
    Get.toNamed(AppRoutes.securityPrivacy);
  }

  void onIdentityKycTap() {
    _showSnackbar(
      'Identity & KYC',
      'Your identity is verified at Tier 2 limits.',
      isSuccess: true,
    );
  }

  void onNotificationsTap() {
    _showSnackbar(
      'Notifications',
      'Manage push notifications and transaction alerts.',
    );
  }

  void onAppearanceTap() {
    _showSnackbar('Appearance', 'Theme customization coming soon.');
  }

  void onLanguageRegionTap() {
    _showSnackbar('Language & Region', 'English (Nigeria) selected.');
  }

  void onHelpSupportTap() {
    _showSnackbar('Help & Support', 'Connecting to 24/7 customer support...');
  }

  Future<void> onLogout() async {
    try {
      await FirebaseAuth.instance.signOut();
    } catch (_) {}
    Get.offAllNamed(AppRoutes.auth);
  }

  void _showSnackbar(String title, String message, {bool isSuccess = false}) {
    if (isSuccess) {
      SnackBarHelper.showSuccess(
        message: message,
        title: title,
        position: SnackPosition.BOTTOM,
        duration: const Duration(seconds: 2),
      );
    } else {
      SnackBarHelper.showInfo(
        message: message,
        title: title,
        position: SnackPosition.BOTTOM,
        duration: const Duration(seconds: 2),
      );
    }
  }
}
