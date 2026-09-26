import 'package:flutter/material.dart';
import 'package:get/get.dart';
import '../views/widgets/confirm_transaction_bottom_sheet.dart';
import '../views/widgets/transaction_pin_bottom_sheet.dart';

class SendAmountController extends GetxController {
  final recipientName = 'Clement Toluwalase Daniel'.obs;
  final recipientAccount = '2212660740 Novabanq'.obs;
  final amount = '2400'.obs;
  final sourceAccountTitle = 'NGN Account Number'.obs;
  final sourceAccountBalance = '100,000'.obs;
  final transactionPin = ''.obs;

  final double exchangeRate = 24.0;

  String get calculatedCedis {
    final parsed = double.tryParse(amount.value.replaceAll(',', '')) ?? 0.0;
    return (parsed / exchangeRate).floor().toString();
  }

  String get beneficiaryReceivesText {
    return 'Beneficiary receives $calculatedCedis cedis';
  }

  void appendDigit(String digit) {
    if (amount.value == '0') {
      amount.value = digit;
    } else if (amount.value.length < 9) {
      amount.value = '${amount.value}$digit';
    }
  }

  void deleteDigit() {
    if (amount.value.length > 1) {
      amount.value = amount.value.substring(0, amount.value.length - 1);
    } else {
      amount.value = '0';
    }
  }

  void clearAmount() {
    amount.value = '0';
  }

  void setPresetAmount(int preset) {
    amount.value = preset.toString();
  }

  final isKeypadVisible = false.obs;

  void openKeypad() {
    isKeypadVisible.value = true;
  }

  void hideKeypad() {
    isKeypadVisible.value = false;
  }

  void toggleKeypad() {
    isKeypadVisible.value = !isKeypadVisible.value;
  }

  void onContinue() {
    hideKeypad();
    Get.snackbar(
      'Transfers pending',
      'Transfers are not available from the API yet.',
      snackPosition: SnackPosition.BOTTOM,
    );
  }

  void showConfirmTransactionSheet() {
    Get.bottomSheet(
      ConfirmTransactionBottomSheet(
        recipientName: recipientName.value,
        fromAccount: 'NGN account',
        amountFromAccount: amount.value,
        amountToBeneficiary: calculatedCedis,
        onConfirm: () {
          Get.back();
          showPinBottomSheet();
        },
      ),
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
    );
  }

  void showPinBottomSheet() {
    transactionPin.value = '';
    Get.bottomSheet(
      Obx(
        () => TransactionPinBottomSheet(
          pin: transactionPin.value,
          onKeyPress: (d) {
            if (transactionPin.value.length < 4) {
              transactionPin.value += d;
            }
          },
          onBackspace: () {
            if (transactionPin.value.isNotEmpty) {
              transactionPin.value = transactionPin.value.substring(
                0,
                transactionPin.value.length - 1,
              );
            }
          },
          onClear: () => transactionPin.value = '',
          onConfirm: () {
            if (transactionPin.value.length == 4) {
              completeTransaction();
            } else {
              Get.snackbar(
                'Enter PIN',
                'Please enter your complete 4-digit PIN',
                snackPosition: SnackPosition.BOTTOM,
                backgroundColor: const Color(0xFF101828),
                colorText: Colors.white,
                duration: const Duration(seconds: 2),
                margin: const EdgeInsets.all(16),
                borderRadius: 12,
              );
            }
          },
        ),
      ),
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
    );
  }

  void completeTransaction() {
    Get.back();
    Get.snackbar(
      'Transfers pending',
      'No transfer was made.',
      snackPosition: SnackPosition.BOTTOM,
    );
  }
}
