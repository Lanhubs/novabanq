import 'package:flutter/material.dart';
import 'package:novabanq/features/send/models/transaction_summary.dart';
import 'transaction_detail_info.dart';
import 'transaction_detail_status.dart';

class TransactionDetailContent extends StatelessWidget {
  final TransactionSummary transaction;
  final VoidCallback onCopyId;

  const TransactionDetailContent({
    super.key,
    required this.transaction,
    required this.onCopyId,
  });

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [

          
          TransactionDetailStatus(transaction: transaction),
          const SizedBox(height: 24),
          TransactionDetailInfo(transaction: transaction, onCopyId: onCopyId),
        ],
      ),
    );
  }
}
