import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class TransactionStatusBadge extends StatelessWidget {
  final String status;
  const TransactionStatusBadge({super.key, required this.status});

  @override
  Widget build(BuildContext context) {
    final normalizedStatus = status.toUpperCase();
    final text = switch (normalizedStatus) {
      'SETTLED' || 'COMPLETED' || 'SUCCESS' => 'Successful',
      'PENDING' => 'Pending',
      'FAILED' => 'Failed',
      'CANCELLED' => 'Cancelled',
      _ => status.replaceAll('_', ' ').toLowerCase(),
    };
    final color = switch (normalizedStatus) {
      'SETTLED' || 'COMPLETED' || 'SUCCESS' => const Color(0xFF067647),
      'PENDING' => const Color(0xFFB54708),
      'FAILED' || 'CANCELLED' => const Color(0xFFB42318),
      _ => const Color(0xFF475467),
    };
    final icon = switch (normalizedStatus) {
      'SETTLED' || 'COMPLETED' || 'SUCCESS' => Icons.check,
      'PENDING' => Icons.schedule,
      'FAILED' || 'CANCELLED' => Icons.close,
      _ => Icons.help_outline,
    };
    return Row(
      mainAxisSize: MainAxisSize.min,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Container(
          width: 18,
          height: 18,
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.12),
            shape: BoxShape.circle,
          ),
          child: Icon(icon, size: 12, color: color),
        ),
        const SizedBox(width: 7),
        Text(
          text,
          style: GoogleFonts.outfit(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: color,
          ),
        ),
      ],
    );
  }
}
