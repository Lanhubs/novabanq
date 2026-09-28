import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class InfoRow extends StatelessWidget {
  final String label;
  final String value;
  final VoidCallback? onCopy;
  final bool highlight;
  final bool incoming;

  const InfoRow(
    this.label,
    this.value, {
    super.key,
    this.onCopy,
    this.highlight = false,
    this.incoming = false,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Text(
            label,
            style: GoogleFonts.outfit(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: const Color(0xFF667085),
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Text(
              value,
              textAlign: TextAlign.right,
              style: GoogleFonts.outfit(
                fontSize: 13,
                fontWeight: highlight ? FontWeight.w600 : FontWeight.w500,
                color: highlight && incoming
                    ? const Color(0xFF027A48)
                    : const Color(0xFF101828),
              ),
            ),
          ),
          if (onCopy != null) ...[
            const SizedBox(width: 8),
            IconButton(
              onPressed: onCopy,
              icon: const Icon(Icons.copy, size: 16),
              color: const Color(0xFF667085),
              tooltip: 'Copy transaction ID',
              constraints: const BoxConstraints(minWidth: 24, minHeight: 24),
              padding: EdgeInsets.zero,
            ),
          ],
        ],
      ),
    );
  }
}
