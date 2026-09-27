import 'package:flutter/material.dart';
import 'package:get/get.dart';
import '../controllers/card_controller.dart';
import 'widgets/card_details_info_card.dart';
import 'widgets/card_details_top_bar.dart';
import 'widgets/virtual_card_back.dart';
import 'widgets/virtual_debit_card.dart';

class CardDetailsScreen extends StatelessWidget {
  const CardDetailsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final controller = Get.isRegistered<CardController>()
        ? Get.find<CardController>()
        : Get.put(CardController());

    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: SingleChildScrollView(
              physics: const BouncingScrollPhysics(),
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  // 1. Top Bar
                  const CardDetailsTopBar(title: 'Card details'),

                  const SizedBox(height: 20),

                  // 2. Front of Debit Card
                  Obx(
                    () => VirtualDebitCard(
                      cardNumber: controller.cardNumber.value,
                      cardHolder: controller.cardHolder.value,
                      expiryDate: controller.expiryDate.value,
                      isFrozen: controller.isCardFrozen.value,
                      isDetailsVisible: true,
                    ),
                  ),

                  const SizedBox(height: 18),

                  // 3. Back of Debit Card
                  Obx(
                    () => VirtualCardBack(
                      cvv: controller.cvv.value,
                      contactNumber: controller.contactNumber.value,
                    ),
                  ),

                  const SizedBox(height: 20),

                  // 4. White Details Information Card
                  Obx(
                    () => CardDetailsInfoCard(
                      accountName: controller.accountName.value,
                      cardNumber: controller.cardNumber.value,
                      expiryDate: controller.expiryDate.value,
                      cvv: controller.cvv.value,
                      onCopyAccountName: controller.copyAccountName,
                      onCopyCardNumber: controller.copyCardNumber,
                      onCopyExpiryDate: controller.copyExpiryDate,
                      onCopyCvv: controller.copyCvv,
                      onControlsTap: controller.onCardControlsAndLimitsTap,
                    ),
                  ),

                  const SizedBox(height: 24),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
