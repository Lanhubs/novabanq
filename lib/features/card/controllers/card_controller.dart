import 'package:flutter/services.dart';
import 'package:get/get.dart';
import 'package:novabanq/app/routes/app_routes.dart';
import 'package:novabanq/core/utils/helpers.dart';
import 'package:novabanq/features/auth/controllers/auth_controller.dart';
import '../models/card_transaction_item.dart';

class CardController extends GetxController {
  final cardNumber = '1213 1372 1362 9012'.obs;
  final cardHolder = 'Kahn Praise Kumasi'.obs;
  final expiryDate = '06/12'.obs;
  final cvv = '923'.obs;
  final accountName = 'Temi Adeyemi'.obs;
  final contactNumber = '01-345-782-901'.obs;
  final hasCard = true.obs;
  final isCardFrozen = false.obs;
  final isDetailsVisible = true.obs;

  @override
  void onInit() {
    super.onInit();
    _loadUserCardInfo();
  }

  void _loadUserCardInfo() {
    if (Get.isRegistered<AuthController>()) {
      final auth = Get.find<AuthController>();
      final first = auth.firstNameController.text.trim();
      final last = auth.lastNameController.text.trim();
      if (first.isNotEmpty || last.isNotEmpty) {
        final name = '$first $last'.trim();
        cardHolder.value = name;
        accountName.value = name;
      }
    }
  }

  final transactions = <CardTransactionItem>[
    const CardTransactionItem(
      title: 'Spotify',
      date: 'Today 12:30PM',
      amount: '-₦1,000.00',
      logoType: 'spotify',
    ),
    const CardTransactionItem(
      title: 'Jumia',
      date: '12-08-2024',
      amount: '-₵2,500.00',
      logoType: 'jumia',
    ),
    const CardTransactionItem(
      title: 'Uber',
      date: '13-07-2024',
      amount: '-₵1,300.00',
      logoType: 'uber',
    ),
  ].obs;

  void onDetailsTap() {
    Get.toNamed(AppRoutes.cardDetails);
  }

  void toggleFreeze() {
    isCardFrozen.value = !isCardFrozen.value;
    if (isCardFrozen.value) {
      SnackBarHelper.showWarning(
        message: 'Your virtual card has been temporarily frozen.',
        title: 'Card Frozen',
        position: SnackPosition.BOTTOM,
        duration: const Duration(seconds: 2),
      );
    } else {
      SnackBarHelper.showSuccess(
        message: 'Your virtual card is now active.',
        title: 'Card Unfrozen',
        position: SnackPosition.BOTTOM,
        duration: const Duration(seconds: 2),
      );
    }
  }

  void copyAccountName() {
    _copyToClipboard(accountName.value, 'Account name copied to clipboard');
  }

  void copyCardNumber() {
    _copyToClipboard(
      cardNumber.value.replaceAll(' ', ''),
      'Card number copied to clipboard',
    );
  }

  void copyExpiryDate() {
    _copyToClipboard(expiryDate.value, 'Expiry date copied to clipboard');
  }

  void copyCvv() {
    _copyToClipboard(cvv.value, 'CVV copied to clipboard');
  }

  void onCardControlsAndLimitsTap() {
    Get.toNamed(AppRoutes.cardControls);
  }

  void onLimitTap() {
    Get.toNamed(AppRoutes.cardControls);
  }

  void onAddCardTap() {
    Get.toNamed(AppRoutes.addCard);
  }

  void onAddNewCard() {
    Get.toNamed(AppRoutes.addCard);
  }

  void onPromoBannerTap() {
    SnackBarHelper.showInfo(
      message: 'Virtual black card feature is coming soon!',
      title: 'Black Card',
      position: SnackPosition.BOTTOM,
      duration: const Duration(seconds: 2),
    );
  }

  void onSeeMoreTap() {
    SnackBarHelper.showInfo(
      message: 'Displaying all recent card transactions.',
      title: 'Transactions',
      position: SnackPosition.BOTTOM,
      duration: const Duration(seconds: 2),
    );
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
