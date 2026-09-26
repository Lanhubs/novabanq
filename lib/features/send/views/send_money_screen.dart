import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:novabanq/features/auth/views/widgets/auth_cta_button.dart';
import '../controllers/send_money_controller.dart';
import 'widgets/recipient_account_card.dart';
import 'widgets/recent_transactions_section.dart';
import 'widgets/send_money_empty_state.dart';
import 'widgets/send_money_top_bar.dart';

class SendMoneyScreen extends GetView<SendMoneyController> {
  const SendMoneyScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: Column(
              children: [
                Expanded(
                  child: SingleChildScrollView(
                    physics: const BouncingScrollPhysics(),
                    padding: const EdgeInsets.symmetric(
                      horizontal: 24,
                      vertical: 16,
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // 1. Top Bar: Back button + Centered Title
                        const SendMoneyTopBar(title: 'Send money'),

                        const SizedBox(height: 28),

                        // 2. Recipient Account Card
                        Obx(
                          () => RecipientAccountCard(
                            accountController:
                                controller.accountNumberController,
                            tagController: controller.accountTagController,
                            selectedBank: controller.selectedBank.value,
                            onSelectBank: () {
                              Get.snackbar(
                                'Select Bank',
                                'Bank selection list coming soon.',
                                snackPosition: SnackPosition.BOTTOM,
                              );
                            },
                          ),
                        ),

                        const SizedBox(height: 28),

                        // 3. Recent Transactions or Empty State
                        Obx(
                          () => controller.hasRecentTransactions
                              ? RecentTransactionsSection(
                                  items: controller.recentTransactions,
                                  onSelect: controller.selectRecipient,
                                )
                              : const SendMoneyEmptyState(),
                        ),

                        const SizedBox(height: 24),
                      ],
                    ),
                  ),
                ),

                // 4. Bottom Continue Button
                Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 24,
                    vertical: 16,
                  ),
                  child: AuthCtaButton(
                    text: 'Continue',
                    onPressed: controller.onContinue,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
