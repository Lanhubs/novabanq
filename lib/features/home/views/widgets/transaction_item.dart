import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:hugeicons/hugeicons.dart';
import 'package:novabanq/app/routes/app_routes.dart';
import 'package:novabanq/features/send/models/transaction_summary.dart';

class TransactionItem extends StatelessWidget {
  final TransactionSummary transaction;
  const TransactionItem({super.key, required this.transaction});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => Get.toNamed(
        AppRoutes.transactionDetail,
        arguments: transaction.transactionId,
      ),
      child: Container(
        margin: const EdgeInsets.only(bottom: 16),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: const Color(0xFFE4E7EC), width: 1),
        ),
        child: Row(
          children: [
            // Transaction icon based on type/direction
            Container(
              width: 50,
              height: 50,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: const Color(0xFFD9D9D9),
                borderRadius: BorderRadius.circular(Get.width * 0.1),
              ),
              child: HugeIcon(
                icon: transaction.isIncoming
                    ? HugeIcons.strokeRoundedArrowDownLeft01
                    : HugeIcons.strokeRoundedArrowUpRight01,
                color: transaction.isIncoming
                    ? const Color(0xFF027A48)
                    : const Color(0xFFD92D20),
                size: 15,
              ),
            ),

            const SizedBox(width: 12),

            // Transaction details
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    transaction.title,
                    style: GoogleFonts.outfit(
                      fontSize: 16,
                      fontWeight: FontWeight.w400,
                      color: const Color(0xFF101828),
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    transaction.subtitle,
                    style: GoogleFonts.outfit(
                      fontSize: 12,
                      fontWeight: FontWeight.w400,
                      color: const Color(0xFF667085),
                    ),
                  ),
                ],
              ),
            ),

            // Amount and date
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  transaction.displayAmount,
                  style: GoogleFonts.outfit(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: transaction.isIncoming
                        ? const Color(0xFF027A48)
                        : const Color(0xFF101828),
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  transaction.dateLabel,
                  style: GoogleFonts.outfit(
                    fontSize: 11,
                    fontWeight: FontWeight.w400,
                    color: const Color(0xFF667085),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
