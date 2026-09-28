import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class SendRecentErrorState extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const SendRecentErrorState({
    super.key,
    required this.message,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            message,
            textAlign: TextAlign.center,
            style: GoogleFonts.outfit(
              fontSize: 13,
              color: const Color(0xFF667085),
            ),
          ),
          TextButton(onPressed: onRetry, child: const Text('Retry')),
        ],
      ),
    );
  }
}
