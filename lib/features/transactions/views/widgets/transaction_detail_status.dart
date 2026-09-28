import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/features/send/models/transaction_summary.dart';
import 'transaction_status_badge.dart';

class TransactionDetailStatus extends StatelessWidget {
  final TransactionSummary transaction;

  const TransactionDetailStatus({super.key, required this.transaction});

  @override
  Widget build(BuildContext context) {
    final status = transaction.status.toUpperCase();
    final recipient =
        transaction.counterparty?.tag
                ?.replaceFirst('@', '')
                .trim()
                .isNotEmpty ==
            true
        ? transaction.counterparty!.tag!.replaceFirst('@', '')
        : transaction.title;
    final direction = transaction.isIncoming ? 'From' : 'To';
    final message = switch (status) {
      'SETTLED' || 'COMPLETED' || 'SUCCESS' =>
        'This transfer has been completed successfully. If the recipient has not received the funds, contact support.',
      'PENDING' => 'This transfer is still processing.',
      'FAILED' => 'This transfer was not completed.',
      'CANCELLED' => 'This transfer was cancelled.',
      _ => 'Transaction status: ${transaction.status}.',
    };

    return Column(
      children: [
        Image.asset(
          'assets/icons/novabanq.png',
          width: 94,
          height: 34,
          fit: BoxFit.contain,
        ),
        const SizedBox(height: 18),
        Text(
          '$direction $recipient',
          textAlign: TextAlign.center,
          style: GoogleFonts.outfit(
            fontSize: 14,
            fontWeight: FontWeight.w500,
            color: const Color(0xFF475467),
          ),
        ),
        const SizedBox(height: 4),
        Text(
          transaction.displayAmount,
          textAlign: TextAlign.center,
          style: GoogleFonts.outfit(
            fontSize: 32,
            fontWeight: FontWeight.w700,
            color: const Color(0xFF101828),
          ),
        ),
        const SizedBox(height: 8),
        TransactionStatusBadge(status: status),
        const SizedBox(height: 16),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          decoration: BoxDecoration(
            color: const Color(0xFFF2F4F7),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Text(
            message,
            style: GoogleFonts.outfit(
              fontSize: 12,
              height: 1.45,
              color: const Color(0xFF475467),
            ),
          ),
        ),
      ],
    );
  }
}
