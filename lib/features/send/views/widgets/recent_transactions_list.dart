import 'package:flutter/material.dart';
import '../../models/recent_transaction_item.dart';
import 'recent_transaction_tile.dart';

class RecentTransactionsList extends StatelessWidget {
  final List<RecentTransactionItem> items;
  final ValueChanged<RecentTransactionItem> onSelect;

  const RecentTransactionsList({
    super.key,
    required this.items,
    required this.onSelect,
  });

  @override
  Widget build(BuildContext context) {
    return ListView.separated(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: items.length,
      separatorBuilder: (context, index) => const SizedBox(height: 2),
      itemBuilder: (context, index) {
        final item = items[index];
        return RecentTransactionTile(
          item: item,
          index: index,
          onTap: () => onSelect(item),
        );
      },
    );
  }
}
