import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../models/card_transaction_item.dart';
import 'card_transaction_tile.dart';

class CardRecentTransactionsSection extends StatelessWidget {
  final List<CardTransactionItem> transactions;
  final VoidCallback onSeeMore;

  const CardRecentTransactionsSection({
    super.key,
    required this.transactions,
    required this.onSeeMore,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Text(
              'Recent transactions',
              style: GoogleFonts.outfit(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: const Color(0xFF101828),
              ),
            ),
            GestureDetector(
              onTap: onSeeMore,
              child: Text(
                'See more',
                style: GoogleFonts.outfit(
                  fontSize: 13,
                  fontWeight: FontWeight.w400,
                  color: const Color(0xFF667085),
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Column(
          children: transactions
              .map((item) => CardTransactionTile(transaction: item))
              .toList(),
        ),
      ],
    );
  }
}
