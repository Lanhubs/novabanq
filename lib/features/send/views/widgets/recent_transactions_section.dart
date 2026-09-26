import 'package:flutter/material.dart';
import '../../models/recent_transaction_item.dart';
import 'recent_transactions_header.dart';
import 'recent_transactions_list.dart';

class RecentTransactionsSection extends StatelessWidget {
  final List<RecentTransactionItem> items;
  final ValueChanged<RecentTransactionItem> onSelect;

  const RecentTransactionsSection({
    super.key,
    required this.items,
    required this.onSelect,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const RecentTransactionsHeader(),
        const SizedBox(height: 14),
        RecentTransactionsList(
          items: items,
          onSelect: onSelect,
        ),
      ],
    );
  }
}
