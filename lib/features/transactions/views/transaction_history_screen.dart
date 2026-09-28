import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/features/home/controllers/home_controller.dart';
import 'package:novabanq/features/home/views/widgets/empty_state.dart';
import 'package:novabanq/features/home/views/widgets/error_state.dart';
import 'package:novabanq/features/home/views/widgets/loading_state.dart';
import 'package:novabanq/features/home/views/widgets/transaction_item.dart';

class TransactionHistoryScreen extends StatefulWidget {
  const TransactionHistoryScreen({super.key});

  @override
  State<TransactionHistoryScreen> createState() =>
      _TransactionHistoryScreenState();
}

class _TransactionHistoryScreenState extends State<TransactionHistoryScreen> {
  late final HomeController controller;

  @override
  void initState() {
    super.initState();
    controller = Get.find<HomeController>();
    controller.loadTransactions(limit: 100, refresh: true);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.white,
        title: Text(
          'Transactions',
          style: GoogleFonts.outfit(
            color: const Color(0xFF101828),
            fontSize: 18,
            fontWeight: FontWeight.w600,
          ),
        ),
        centerTitle: true,
      ),
      body: Obx(() {
        if (controller.isTransactionsLoading.value &&
            controller.transactions.isEmpty) {
          return const LoadingState();
        }
        if (controller.transactionsError.value.isNotEmpty &&
            controller.transactions.isEmpty) {
          return ErrorState(
            onRetry: () =>
                controller.loadTransactions(limit: 100, refresh: true),
          );
        }
        if (controller.transactions.isEmpty) return const EmptyState();
        return RefreshIndicator(
          onRefresh: () =>
              controller.loadTransactions(limit: 100, refresh: true),
          child: ListView.builder(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
            itemCount: controller.transactions.length,
            itemBuilder: (context, index) => TransactionItem(
              key: ValueKey(controller.transactions[index].transactionId),
              transaction: controller.transactions[index],
            ),
          ),
        );
      }),
    );
  }
}
