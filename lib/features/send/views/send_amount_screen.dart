import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:novabanq/core/widgets/custom_numeric_keypad.dart';
import 'package:novabanq/features/auth/views/widgets/auth_cta_button.dart';
import '../controllers/send_amount_controller.dart';
import 'widgets/amount_recipient_card.dart';
import 'widgets/beneficiary_receives_notice.dart';
import 'widgets/preset_amount_chips_row.dart';
import 'widgets/send_amount_display.dart';
import 'widgets/send_money_top_bar.dart';
import 'widgets/send_source_account_card.dart';

class SendAmountScreen extends GetView<SendAmountController> {
  const SendAmountScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: LayoutBuilder(
                builder: (context, constraints) {
                  return SingleChildScrollView(
                    physics: const BouncingScrollPhysics(),
                    padding: const EdgeInsets.symmetric(
                      horizontal: 20.0,
                      vertical: 12.0,
                    ),
                    child: ConstrainedBox(
                      constraints: BoxConstraints(
                        minHeight: constraints.maxHeight,
                      ),
                      child: IntrinsicHeight(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            // Top Bar
                            const SendMoneyTopBar(title: 'Send money'),

                            const SizedBox(height: 24),

                            // Recipient Card
                            Obx(
                              () => AmountRecipientCard(
                                name: controller.recipientName.value,
                                accountInfo: controller.recipientAccount.value,
                              ),
                            ),

                            const SizedBox(height: 24),

                            // Centered Amount Display with tap to toggle custom keypad
                            Obx(
                              () => SendAmountDisplay(
                                amount: controller.amount.value,
                                onTap: controller.toggleKeypad,
                              ),
                            ),

                            const SizedBox(height: 12),

                            // Preset Quick Amount Chips
                            PresetAmountChipsRow(
                              onSelectPreset: controller.setPresetAmount,
                            ),

                            const SizedBox(height: 28),

                            // Source Account Card
                            Obx(
                              () => SendSourceAccountCard(
                                title: controller.sourceAccountTitle.value,
                                balance: controller.sourceAccountBalance.value,
                                onChange: () {},
                              ),
                            ),

                            const SizedBox(height: 8),

                            // Beneficiary Receives Notice
                            Obx(
                              () => BeneficiaryReceivesNotice(
                                text: controller.beneficiaryReceivesText,
                              ),
                            ),

                            const Spacer(),

                            const SizedBox(height: 16),

                            // Continue Button
                            AuthCtaButton(
                              text: 'Continue',
                              onPressed: controller.onContinue,
                            ),

                            const SizedBox(height: 12),
                          ],
                        ),
                      ),
                    ),
                  );
                },
              ),
            ),

            // Pinned custom keypad behaving like a native keyboard widget
            Obx(
              () => controller.isKeypadVisible.value
                  ? CustomNumericKeypad(
                      onKeyPress: controller.appendDigit,
                      onBackspace: controller.deleteDigit,
                      onClear: controller.clearAmount,
                    )
                  : const SizedBox.shrink(),
            ),
          ],
        ),
      ),
    );
  }
}
