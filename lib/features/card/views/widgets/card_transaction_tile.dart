import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../models/card_transaction_item.dart';
import 'card_brand_badge.dart';

class CardTransactionTile extends StatelessWidget {
  final CardTransactionItem transaction;

  const CardTransactionTile({
    super.key,
    required this.transaction,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8.0),
      child: Row(
        children: [
          CardBrandBadge(logoType: transaction.logoType),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  transaction.title,
                  style: GoogleFonts.outfit(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    color: const Color(0xFF101828),
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  transaction.date,
                  style: GoogleFonts.outfit(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w400,
                    color: const Color(0xFF667085),
                  ),
                ),
              ],
            ),
          ),
          Text(
            transaction.amount,
            style: GoogleFonts.outfit(
              fontSize: 14.5,
              fontWeight: FontWeight.w600,
              color: const Color(0xFFE05656),
            ),
          ),
        ],
      ),
    );
  }
}
