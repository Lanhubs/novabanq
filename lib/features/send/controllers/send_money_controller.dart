import 'package:flutter/material.dart';
import 'package:get/get.dart';
import '../models/recent_transaction_item.dart';

class SendMoneyController extends GetxController {
  final accountNumberController = TextEditingController();
  final accountTagController = TextEditingController();
  final selectedBank = ''.obs;

  final recentTransactions = <RecentTransactionItem>[].obs;

  bool get hasRecentTransactions => recentTransactions.isNotEmpty;

  void selectBank(String bank) {
    selectedBank.value = bank;
  }

  void selectRecipient(RecentTransactionItem item) {
    if (item.subtitle.startsWith('@')) {
      accountTagController.text = item.subtitle.substring(1);
      accountNumberController.clear();
    } else {
      accountNumberController.text = item.subtitle;
      accountTagController.clear();
    }
  }

  void onContinue() {
    Get.snackbar(
      'Transfers pending',
      'Recipient lookup and transfers are not available from the API yet.',
      snackPosition: SnackPosition.BOTTOM,
    );
  }

  @override
  void onClose() {
    accountNumberController.dispose();
    accountTagController.dispose();
    super.onClose();
  }
}
