import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class TransferDetailRow extends StatelessWidget {
  final String label;
  final String value;
  final Color? valueColor;
  final bool showCopyIcon;
  final VoidCallback? onCopy;

  const TransferDetailRow({
    super.key,
    required this.label,
    required this.value,
    this.valueColor,
    this.showCopyIcon = false,
    this.onCopy,
  });

  @override
  Widget build(BuildContext context) {
    final effectiveColor = valueColor ?? const Color(0xFF101828);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 9.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: GoogleFonts.outfit(
              fontSize: 13,
              fontWeight: FontWeight.w400,
              color: const Color(0xFF667085),
            ),
          ),
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                value,
                style: GoogleFonts.outfit(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: effectiveColor,
                ),
              ),
              if (showCopyIcon) ...[
                const SizedBox(width: 6),
                InkWell(
                  onTap: onCopy,
                  borderRadius: BorderRadius.circular(4),
                  child: const Padding(
                    padding: EdgeInsets.all(2.0),
                    child: Icon(
                      Icons.copy_rounded,
                      size: 14,
                      color: Color(0xFF667085),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }
}
