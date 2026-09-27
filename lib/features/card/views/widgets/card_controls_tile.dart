import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class CardControlsTile extends StatelessWidget {
  final VoidCallback onTap;

  const CardControlsTile({
    super.key,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 10.0),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Text(
              'Card controls and limits',
              style: GoogleFonts.outfit(
                fontSize: 13.5,
                fontWeight: FontWeight.w500,
                color: const Color(0xFF344054),
              ),
            ),
            const Icon(
              Icons.chevron_right_rounded,
              size: 20,
              color: Color(0xFF667085),
            ),
          ],
        ),
      ),
    );
  }
}
