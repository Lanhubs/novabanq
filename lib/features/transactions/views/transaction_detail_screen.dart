import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/features/home/views/widgets/loading_state.dart';
import '../controllers/transaction_detail_controller.dart';
import 'widgets/transaction_detail_content.dart';
import 'widgets/transaction_detail_empty_state.dart';
import 'widgets/transaction_detail_error_state.dart';

class TransactionDetailScreen extends StatefulWidget {
  const TransactionDetailScreen({super.key});

  @override
  State<TransactionDetailScreen> createState() =>
      _TransactionDetailScreenState();
}

class _TransactionDetailScreenState extends State<TransactionDetailScreen> {
  late final TransactionDetailController controller;

  @override
  void initState() {
    super.initState();
    controller = Get.put(
      TransactionDetailController(
        transactionId: Get.arguments is String ? Get.arguments as String : '',
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: BackButton(
          onPressed: controller.goBack,
          color: const Color(0xFF101828),
        ),
        title: Text(
          'Transaction Details',
          style: GoogleFonts.outfit(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: const Color(0xFF101828),
          ),
        ),
        centerTitle: true,
      ),
      body: Obx(() {
        final transaction = controller.transaction.value;
        if (controller.isLoading.value && transaction == null) {
          return const LoadingState();
        }
        if (controller.error.value.isNotEmpty && transaction == null) {
          return TransactionDetailErrorState(
            message: controller.error.value,
            onRetry: controller.onRetry,
          );
        }
        if (transaction == null) return const TransactionDetailEmptyState();
        return TransactionDetailContent(
          transaction: transaction,
          onCopyId: controller.copyTransactionId,
        );
      }),
    );
  }
}
