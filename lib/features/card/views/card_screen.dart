import 'package:flutter/material.dart';
import 'package:get/get.dart';
import '../controllers/card_controller.dart';
import 'widgets/card_actions_row.dart';
import 'widgets/card_black_promo_banner.dart';
import 'widgets/card_recent_transactions_section.dart';
import 'widgets/empty_card_view.dart';
import 'widgets/virtual_debit_card.dart';

class CardScreen extends StatelessWidget {
  const CardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final controller = Get.isRegistered<CardController>()
        ? Get.find<CardController>()
        : Get.put(CardController());

    return Obx(() {
      if (!controller.hasCard.value) {
        return const SafeArea(
          bottom: false,
          child: EmptyCardView(),
        );
      }

      return SafeArea(
        bottom: false,
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: SingleChildScrollView(
              physics: const BouncingScrollPhysics(),
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  // 1. Virtual Debit Card
                  Obx(
                    () => VirtualDebitCard(
                      cardNumber: controller.cardNumber.value,
                      cardHolder: controller.cardHolder.value,
                      expiryDate: controller.expiryDate.value,
                      isFrozen: controller.isCardFrozen.value,
                      isDetailsVisible: controller.isDetailsVisible.value,
                    ),
                  ),

                  const SizedBox(height: 24),

                  // 2. Action Buttons: Details, Freeze, Limit, Add card
                  Obx(
                    () => CardActionsRow(
                      onDetailsTap: controller.onDetailsTap,
                      onFreezeTap: controller.toggleFreeze,
                      onLimitTap: controller.onLimitTap,
                      onAddCardTap: controller.onAddCardTap,
                      isFrozen: controller.isCardFrozen.value,
                    ),
                  ),

                  const SizedBox(height: 24),

                  // 3. Layered Stack Promo Banner
                  CardBlackPromoBanner(
                    onTap: controller.onPromoBannerTap,
                  ),

                  const SizedBox(height: 26),

                  // 4. Recent Transactions
                  CardRecentTransactionsSection(
                    transactions: controller.transactions,
                    onSeeMore: controller.onSeeMoreTap,
                  ),

                  const SizedBox(height: 20),
                ],
              ),
            ),
          ),
        ),
      );
    });
  }
}