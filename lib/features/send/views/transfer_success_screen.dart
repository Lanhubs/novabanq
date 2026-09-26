import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:novabanq/features/auth/views/widgets/auth_cta_button.dart';
import '../controllers/transfer_success_controller.dart';
import 'widgets/send_money_top_bar.dart';
import 'widgets/transfer_details_section.dart';
import 'widgets/transfer_success_header.dart';

class TransferSuccessScreen extends GetView<TransferSuccessController> {
  const TransferSuccessScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20.0, vertical: 12.0),
          child: Column(
            children: [
              // Top Bar with back button only
              const SendMoneyTopBar(title: ''),

              const SizedBox(height: 20),

              // Success Illustration & Heading
              const TransferSuccessHeader(),

              const SizedBox(height: 36),

              // Transaction Details
              Obx(
                () => TransferDetailsSection(
                  status: controller.status.value,
                  accountName: controller.accountName.value,
                  accountNumber: controller.accountNumber.value,
                  dateTime: controller.dateTime.value,
                  transactionId: controller.transactionId.value,
                  onCopyTransactionId: controller.copyTransactionId,
                ),
              ),

              const Spacer(),

              // Back to home button
              AuthCtaButton(
                text: 'Back to home',
                onPressed: controller.backToHome,
              ),

              const SizedBox(height: 12),
            ],
          ),
        ),
      ),
    );
  }
}
