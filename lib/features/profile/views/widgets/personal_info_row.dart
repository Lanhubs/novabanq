import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class PersonalInfoRow extends StatelessWidget {
  final String label;
  final String value;
  final IconData? actionIcon;
  final VoidCallback? onAction;

  const PersonalInfoRow({
    super.key,
    required this.label,
    required this.value,
    this.actionIcon,
    this.onAction,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 14.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          // Left Label
          Text(
            label,
            style: GoogleFonts.outfit(
              fontSize: 13.5,
              fontWeight: FontWeight.w700,
              color: const Color(0xFF101828),
            ),
          ),

          // Right Value & Action Icon
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                value,
                style: GoogleFonts.outfit(
                  fontSize: 13.5,
                  fontWeight: FontWeight.w400,
                  color: const Color(0xFF667085),
                ),
              ),
              if (actionIcon != null) ...[
                const SizedBox(width: 6),
                GestureDetector(
                  onTap: onAction,
                  behavior: HitTestBehavior.opaque,
                  child: Icon(
                    actionIcon,
                    size: 16,
                    color: const Color(0xFF667085),
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
