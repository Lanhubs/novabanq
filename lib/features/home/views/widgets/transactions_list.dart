import 'package:flutter/material.dart';
import 'package:novabanq/features/home/controllers/home_controller.dart';
import 'package:novabanq/features/home/views/widgets/transaction_item.dart';

class TransactionsList extends StatelessWidget {
  final HomeController controller;
  const TransactionsList({super.key, required this.controller});

  @override
  Widget build(BuildContext context) {
    // Show maximum 3 transactions for home screen
    final displayTransactions = controller.transactions.take(3).toList();

    return Column(
      children: [
        // Transaction list
        ...displayTransactions.map(
          (transaction) => TransactionItem(transaction: transaction),
        ),

        // Loading indicator for additional transactions
        if (controller.isTransactionsLoading.value &&
            controller.transactions.isNotEmpty)
          const Padding(
            padding: EdgeInsets.only(top: 16.0),
            child: Center(
              child: SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: Color(0xFF1570EF),
                ),
              ),
            ),
          ),
      ],
    );
  }

}