import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/features/send/views/widgets/send_money_top_bar.dart';
import '../controllers/receive_money_controller.dart';
import '../widgets/receive_bank_details_card.dart';
import '../widgets/receive_tag_card.dart';

class ReceiveMoneyScreen extends GetView<ReceiveMoneyController> {
  const ReceiveMoneyScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFFFFF),
      body: SafeArea(
        child: SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // 1. Top Bar
              const SendMoneyTopBar(title: 'Receive money'),

              const SizedBox(height: 24),

              // 2. Your Account @tag Card
              Obx(
                () => ReceiveTagCard(
                  tag: controller.tag.value,
                  onCopyTag: controller.copyTag,
                  onShareLink: controller.shareLink,
                ),
              ),

              const SizedBox(height: 28),

              // 3. Section Title
              Obx(
                () => Text(
                  'Your ${controller.currency.value} bank details',
                  style: GoogleFonts.outfit(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    color: const Color(0xFF101828),
                  ),
                ),
              ),

              const SizedBox(height: 12),

              // 4. Bank Details Card
              Obx(
                () => ReceiveBankDetailsCard(
                  accountName: controller.accountName.value,
                  accountNumber: controller.accountNumber.value,
                  bankName: controller.bankName.value,
                  onCopyName: controller.copyAccountName,
                  onCopyNumber: controller.copyAccountNumber,
                  onCopyBank: controller.copyBankName,
                ),
              ),

              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }
}
