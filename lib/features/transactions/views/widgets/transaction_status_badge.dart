import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class TransactionStatusBadge extends StatelessWidget {
  final String status;
  const TransactionStatusBadge({super.key, required this.status});

  @override
  Widget build(BuildContext context) {
    final text = switch (status) {
      'SETTLED' || 'COMPLETED' || 'SUCCESS' => 'Completed',
      'PENDING' => 'Pending',
      'FAILED' => 'Failed',
      'CANCELLED' => 'Cancelled',
      _ => status.replaceAll('_', ' ').toLowerCase(),
    };
    return Row(
      spacing: 10,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Container(
          width: 20,
          height: 20,
          decoration: BoxDecoration(
            color: Colors.white,
            shape: BoxShape.circle,
          ),
          child: Icon(
            text == "completed"
                ? Icons.check
                : text == "pending"
                ? Icons.hourglass_bottom
                : text == "failed"
                ? Icons.close
                : text == "cancelled"
                ? Icons.cancel
                : Icons.help_outline,
            size: 12,
            color: Colors.white.withValues(alpha: 0.9),
          ),
        ),
        Text(
          text,
          style: GoogleFonts.outfit(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: Colors.white,
          ),
        ),
      ],
    );
  }
}
