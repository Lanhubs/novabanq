import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:novabanq/core/utils/helpers.dart';
import 'package:novabanq/core/network/api_client.dart';
import 'package:novabanq/core/network/transactions_api.dart';
import '../models/recent_transaction_item.dart';
import '../views/widgets/select_corridor_bottom_sheet.dart';

class SendMoneyController extends GetxController {
  final accountNumberController = TextEditingController();
  final accountTagController = TextEditingController();
  final selectedBank = ''.obs;

  final recentTransactions = <RecentTransactionItem>[].obs;
  final isRecentLoading = false.obs;
  final recentError = ''.obs;

  @override
  void onInit() {
    super.onInit();
    loadRecentTransactions();
  }

  Future<void> loadRecentTransactions() async {
    if (isRecentLoading.value) return;
    isRecentLoading.value = true;
    recentError.value = '';
    try {
      final page = await TransactionsApi(
        ApiClient(),
      ).getTransactions(limit: 20);
      final seen = <String>{};
      recentTransactions.assignAll(
        page.items
            .where(
              (item) =>
                  item.transactionType == 'TRANSFER' &&
                  item.direction == 'OUT' &&
                  item.counterparty?.tag?.isNotEmpty == true,
            )
            .where((item) => seen.add(item.counterparty!.tag!))
            .take(6)
            .map(
              (item) => RecentTransactionItem(
                name: item.title,
                subtitle: item.subtitle,
                date: item.dateLabel,
              ),
            ),
      );
    } on ApiFailure catch (failure) {
      recentError.value = failure.message;
    } catch (_) {
      recentError.value = 'Unable to load recent recipients.';
    } finally {
      isRecentLoading.value = false;
    }
  }

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
    final tag = accountTagController.text.trim();
    final recipient = (tag.startsWith('@') ? tag.substring(1) : tag)
        .toLowerCase();

    if (recipient.isEmpty) {
      SnackBarHelper.showValidationError(
        message:
            'Transfers currently require a recipient tag (e.g. @name.country).',
      );
      return;
    }

    final parts = recipient.split('.');
    if (parts.length != 2 ||
        parts.first.isEmpty ||
        parts.last.length != 2 ||
        parts.last.codeUnits.any((unit) => unit < 97 || unit > 122) ||
        parts.first.contains(' ')) {
      SnackBarHelper.showValidationError(
        message: 'Enter the full recipient tag, including its country suffix.',
      );
      return;
    }

    SelectCorridorBottomSheet.show(Get.context!, recipientTag: recipient);
  }

  @override
  void onClose() {
    accountNumberController.dispose();
    accountTagController.dispose();
    super.onClose();
  }
}
