import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/features/send/models/transaction_summary.dart';
import 'transaction_status_badge.dart';
import 'transaction_status_icon.dart';

class TransactionDetailStatus extends StatelessWidget {
  final TransactionSummary transaction;

  const TransactionDetailStatus({super.key, required this.transaction});

  @override
  Widget build(BuildContext context) {
    final status = transaction.status.toUpperCase();
    final colors = switch (status) {
      'SETTLED' ||
      'COMPLETED' ||
      'SUCCESS' => const [Color(0xFF027A48), Color(0xFF05603A)],
      'PENDING' => const [Color(0xFFF79009), Color(0xFFDC6803)],
      'FAILED' || 'CANCELLED' => const [Color(0xFFD92D20), Color(0xFFB42318)],
      _ => const [Color(0xFF344054), Color(0xFF1D2939)],
    };
    return SizedBox(
     
      child: Column(
        children: [
          TransactionStatusIcon(status: status),
          const SizedBox(height: 16),
          Text(
            transaction.displayAmount,
            style: GoogleFonts.outfit(
              fontSize: 32,
              fontWeight: FontWeight.w700,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            transaction.title,
            textAlign: TextAlign.center,
            style: GoogleFonts.outfit(
              fontSize: 16,
              fontWeight: FontWeight.w500,
              color: Colors.white.withValues(alpha: 0.9),
            ),
          ),
          const SizedBox(height: 12),
          TransactionStatusBadge(status: status),
        ],
      ),
    );
  }
}
