import 'package:flutter/material.dart';

class TransactionStatusIcon extends StatelessWidget {
  final String status;
  const TransactionStatusIcon({super.key, required this.status});

  @override
  Widget build(BuildContext context) {
    final icon = switch (status) {
      'SETTLED' || 'COMPLETED' || 'SUCCESS' => Icons.check_circle,
      'PENDING' => Icons.schedule,
      'FAILED' || 'CANCELLED' => Icons.cancel,
      _ => Icons.info,
    };
    return Container(
      width: 64,
      height: 64,
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.2),
        shape: BoxShape.circle,
      ),
      child: Icon(icon, size: 32, color: Colors.white),
    );
  }
}
