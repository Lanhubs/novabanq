import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../models/recent_transaction_item.dart';
import 'recent_transaction_avatar.dart';

class RecentTransactionTile extends StatelessWidget {
  final RecentTransactionItem item;
  final int index;
  final VoidCallback onTap;

  const RecentTransactionTile({
    super.key,
    required this.item,
    required this.index,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 10),
        child: Row(
          children: [
            // Avatar
            RecentTransactionAvatar(
              name: item.name,
              index: index,
            ),

            const SizedBox(width: 14),

            // Name + Account/Tag
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    item.name,
                    style: GoogleFonts.outfit(
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                      color: const Color(0xFF101828),
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    item.subtitle,
                    style: GoogleFonts.outfit(
                      fontSize: 13,
                      fontWeight: FontWeight.w400,
                      color: const Color(0xFF667085),
                    ),
                  ),
                ],
              ),
            ),

            // Date
            Text(
              item.date,
              style: GoogleFonts.outfit(
                fontSize: 12,
                fontWeight: FontWeight.w400,
                color: const Color(0xFF667085),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
