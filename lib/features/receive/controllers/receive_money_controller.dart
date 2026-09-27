import 'package:flutter/services.dart';
import 'package:get/get.dart';
import 'package:novabanq/core/network/api_client.dart';
import 'package:novabanq/core/network/funding_api.dart';
import 'package:novabanq/core/utils/helpers.dart';
import 'package:novabanq/core/network/profile_api.dart';
import '../models/virtual_account_info.dart';

class ReceiveMoneyController extends GetxController {
  final tag = 'danclem.ng'.obs;
  final accountName = 'Temi Adeyemi'.obs;
  final accountNumber = '2002182918'.obs;
  final bankName = 'Novabanq MFB'.obs;
  final currency = 'NGN'.obs;
  final isLoading = false.obs;

  FundingApi get fundingApi => _fundingApi ??= FundingApi(ApiClient());
  FundingApi? _fundingApi;

  ProfileApi get profileApi => _profileApi ??= ProfileApi(ApiClient());
  ProfileApi? _profileApi;

  @override
  void onInit() {
    super.onInit();
    loadReceiveDetails();
  }

  Future<void> loadReceiveDetails() async {
    try {
      isLoading.value = true;
      final profileData = await profileApi.profile().catchError(
        (_) => <String, dynamic>{},
      );

      VirtualAccountInfo? vaData;
      try {
        vaData = await fundingApi.getVirtualAccount();
      } catch (_) {
        vaData = null;
      }

      if (profileData['tag'] != null &&
          profileData['tag'].toString().isNotEmpty) {
        tag.value = profileData['tag'].toString();
      }

      final fName = profileData['first_name']?.toString() ?? '';
      final lName = profileData['last_name']?.toString() ?? '';
      if (fName.isNotEmpty || lName.isNotEmpty) {
        accountName.value = '$fName $lName'.trim();
      }

      if (vaData != null) {
        if (vaData.accountNumber.isNotEmpty) {
          accountNumber.value = vaData.accountNumber;
        }
        if (vaData.bankName.isNotEmpty) {
          bankName.value = vaData.bankName;
        }
        if (vaData.accountName.isNotEmpty) {
          accountName.value = vaData.accountName;
        }
        if (vaData.currency.isNotEmpty) {
          currency.value = vaData.currency;
        }
      }
    } catch (_) {
      // Keep sensible defaults matching design
    } finally {
      isLoading.value = false;
    }
  }

  void copyTag() {
    final t = tag.value.startsWith('@') ? tag.value : '@${tag.value}';
    _copyToClipboard(t, 'Tag copied to clipboard');
  }

  void shareLink() {
    final t = tag.value.startsWith('@') ? tag.value.substring(1) : tag.value;
    final link = 'https://novabanq.app/pay/@$t';
    _copyToClipboard(link, 'Payment link copied to clipboard');
  }

  void copyAccountName() {
    _copyToClipboard(accountName.value, 'Account name copied to clipboard');
  }

  void copyAccountNumber() {
    _copyToClipboard(accountNumber.value, 'Account number copied to clipboard');
  }

  void copyBankName() {
    _copyToClipboard(bankName.value, 'Bank name copied to clipboard');
  }

  void _copyToClipboard(String text, String message) {
    Clipboard.setData(ClipboardData(text: text));
    SnackBarHelper.showSuccess(
      message: message,
      title: 'Copied',
      position: SnackPosition.BOTTOM,
      duration: const Duration(seconds: 2),
    );
  }
}
