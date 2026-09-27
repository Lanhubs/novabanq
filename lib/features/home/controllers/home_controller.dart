import 'package:flutter/services.dart';
import 'package:get/get.dart';
import 'package:novabanq/app/routes/app_routes.dart';
import 'package:novabanq/core/utils/helpers.dart';
import 'package:novabanq/features/auth/controllers/auth_controller.dart';
import 'package:novabanq/core/network/api_client.dart';
import 'package:novabanq/core/network/profile_api.dart';
import 'package:novabanq/core/network/transfer_api.dart';
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

  final balanceAmount = '—'.obs;
  final accountTag = ''.obs;

  // Selected country & currency
  final selectedCountryCurrency = kHomeSupportedCurrencies.first.obs;
  final selectedCurrency = 'NGN'.obs;

  String get currencySymbol => selectedCountryCurrency.value.symbol;
  String get countryCode => selectedCountryCurrency.value.countryCode;

  @override
  void onReady() {
    super.onReady();
    loadAccount();
    loadProfile().then((_) {
      if (Get.arguments is Map &&
          (Get.arguments as Map)['fromSignUp'] == true &&
          profileError.value.isEmpty &&
          accountTag.value.isEmpty) {
        showAccountTagSheet();
      }
    });
  }

  Future<void> loadAccount() async {
    try {
      final account = await TransferApi(ApiClient()).getAccount();
      balanceAmount.value = account.balanceDisplay;
      final matching = kHomeSupportedCurrencies
          .where((item) => item.currencyCode == account.currency)
          .toList();
      if (matching.isNotEmpty) selectCountryCurrency(matching.first);
    } catch (_) {
      balanceAmount.value = '—';
    }
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
    SnackBarHelper.showSuccess(
      message: 'Account number copied to clipboard',
      title: 'Copied',
      position: SnackPosition.BOTTOM,
      duration: const Duration(seconds: 2),
    );
  }

  void onNotificationTap() {
    SnackBarHelper.showInfo(
      message: 'You have no new notifications.',
      title: 'Notifications',
      position: SnackPosition.TOP,
      duration: const Duration(seconds: 2),
    );
  }

  void onAddAccountTag() {
    showAccountTagSheet();
  }

  void onQuickAction(String action) {
    if (action == 'Send') {
      Get.toNamed(AppRoutes.sendMoney);
    } else if (action == 'Receive') {
      Get.toNamed(AppRoutes.receiveMoney);
    }
  }

  void onSelectNavTab(int index) {
    currentNavIndex.value = index;
  }
}
