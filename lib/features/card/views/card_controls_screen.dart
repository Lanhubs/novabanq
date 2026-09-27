import 'package:flutter/material.dart';
import 'package:get/get.dart';
import '../controllers/card_controls_controller.dart';
import 'widgets/card_control_tile.dart';
import 'widgets/card_details_top_bar.dart';

class CardControlsScreen extends StatelessWidget {
  const CardControlsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final controller = Get.isRegistered<CardControlsController>()
        ? Get.find<CardControlsController>()
        : Get.put(CardControlsController());

    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.start,
                children: [
                  const CardDetailsTopBar(title: 'Card controls'),
                  const SizedBox(height: 24),
                  Obx(
                    () => CardControlTile(
                      title: 'Online payments',
                      subtitle: 'E-commerce and websites',
                      value: controller.isOnlinePaymentsEnabled.value,
                      onChanged: controller.toggleOnlinePayments,
                    ),
                  ),
                  Obx(
                    () => CardControlTile(
                      title: 'International use',
                      subtitle: 'Cross border transaction',
                      value: controller.isInternationalUseEnabled.value,
                      onChanged: controller.toggleInternationalUse,
                    ),
                  ),
                  Obx(
                    () => CardControlTile(
                      title: 'ATM withdrawals',
                      subtitle: 'Physical cash access',
                      value: controller.isAtmWithdrawalsEnabled.value,
                      onChanged: controller.toggleAtmWithdrawals,
                    ),
                  ),
                  Obx(
                    () => CardControlTile(
                      title: 'Contactless',
                      subtitle: 'Tap to pay',
                      value: controller.isContactlessEnabled.value,
                      onChanged: controller.toggleContactless,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
