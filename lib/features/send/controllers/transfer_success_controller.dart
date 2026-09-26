import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:get/get.dart';
import 'package:novabanq/app/routes/app_routes.dart';

class TransferSuccessController extends GetxController {
  final status = 'Completed'.obs;
  final accountName = 'Clement Toluwalase Daniel'.obs;
  final accountNumber = '2914099287'.obs;
  final dateTime = '12-09-2023/08:12'.obs;
  final transactionId = 'N25D988862519751'.obs;

  void copyTransactionId() {
    Clipboard.setData(ClipboardData(text: transactionId.value));
    Get.snackbar(
      'Copied',
      'Transaction ID copied to clipboard',
      snackPosition: SnackPosition.BOTTOM,
      duration: const Duration(seconds: 2),
      margin: const EdgeInsets.all(16),
      borderRadius: 12,
    );
  }

  void backToHome() {
    Get.offAllNamed(AppRoutes.home);
  }
}
