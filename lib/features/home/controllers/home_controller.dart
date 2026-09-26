import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:get/get.dart';
import 'package:novabanq/features/auth/controllers/auth_controller.dart';
import 'package:novabanq/core/network/api_client.dart';
import 'package:novabanq/core/network/profile_api.dart';
import 'package:novabanq/core/services/firebase_bootstrap.dart';
import '../models/home_country_currency.dart';
import '../views/widgets/create_account_tag_bottom_sheet.dart';
import '../views/widgets/create_account_tag_input_bottom_sheet.dart';

class HomeController extends GetxController {
  final isBalanceVisible = true.obs;
  final currentNavIndex = 0.obs;
  final profile = <String, dynamic>{}.obs;
  final isLoading = false.obs;
  final profileError = ''.obs;
  String get accountNumber {
    final number = profile['account_number']?.toString() ?? '';
    return number.length == 10
        ? '${number.substring(0, 3)}***${number.substring(6)}'
        : 'Pending';
  }

  final balanceAmount = '—';
  final accountTag = ''.obs;

  // Selected country & currency
  final selectedCountryCurrency = kHomeSupportedCurrencies.first.obs;
  final selectedCurrency = 'NGN'.obs;

  String get currencySymbol => selectedCountryCurrency.value.symbol;
  String get countryCode => selectedCountryCurrency.value.countryCode;

  @override
  void onReady() {
    super.onReady();
    loadProfile().then((_) {
      if (Get.arguments is Map &&
          (Get.arguments as Map)['fromSignUp'] == true &&
          profileError.value.isEmpty &&
          accountTag.value.isEmpty) {
        showAccountTagSheet();
      }
    });
  }

  Future<void> loadProfile() async {
    if (!FirebaseBootstrap.ready) {
      profileError.value = 'Firebase setup is required.';
      return;
    }
    isLoading.value = true;
    try {
      final data = await ProfileApi(ApiClient()).profile();
      profile.assignAll(data);
      accountTag.value = data['tag']?.toString() ?? '';
      final matching = kHomeSupportedCurrencies
          .where((item) => item.countryCode == data['country'])
          .toList();
      if (matching.isNotEmpty) selectCountryCurrency(matching.first);
      profileError.value = '';
    } on ApiFailure catch (failure) {
      profileError.value = failure.message;
    } finally {
      isLoading.value = false;
    }
  }

  void showAccountTagSheet() {
    if (Get.context != null) {
      CreateAccountTagBottomSheet.show(Get.context!);
    }
  }

  void showAccountTagInputSheet() {
    if (Get.context != null) {
      CreateAccountTagInputBottomSheet.show(Get.context!);
    }
  }

  void selectCountryCurrency(HomeCountryCurrency item) {
    selectedCountryCurrency.value = item;
    selectedCurrency.value = item.currencyCode;
  }

  String get greetingName {
    if (Get.isRegistered<AuthController>()) {
      final auth = Get.find<AuthController>();
      final name = auth.firstNameController.text.trim();
      if (name.isNotEmpty) {
        return name;
      }
    }
    return profile['first_name']?.toString() ?? 'there';
  }

  void toggleBalanceVisibility() {
    isBalanceVisible.value = !isBalanceVisible.value;
  }

  void copyAccountNumber() {
    final number = profile['account_number']?.toString();
    if (number == null || number.isEmpty) return;
    Clipboard.setData(ClipboardData(text: number));
    Get.snackbar(
      'Copied',
      'Account number copied to clipboard',
      snackPosition: SnackPosition.BOTTOM,
      backgroundColor: const Color(0xFF005100),
      colorText: Colors.white,
      duration: const Duration(seconds: 2),
      margin: const EdgeInsets.all(16),
      borderRadius: 12,
    );
  }

  void onNotificationTap() {
    Get.snackbar(
      'Notifications',
      'You have no new notifications.',
      snackPosition: SnackPosition.TOP,
      duration: const Duration(seconds: 2),
    );
  }

  void onAddAccountTag() {
    showAccountTagSheet();
  }

  void onQuickAction(String action) {
    if (action == 'Send') {
      Get.snackbar(
        'Transfers pending',
        'Transfers are not available yet.',
        snackPosition: SnackPosition.BOTTOM,
      );
      return;
    }
    Get.snackbar(
      action,
      '$action is not available from the API yet.',
      snackPosition: SnackPosition.BOTTOM,
      duration: const Duration(seconds: 2),
    );
  }

  void onSelectNavTab(int index) {
    currentNavIndex.value = index;
  }
}
