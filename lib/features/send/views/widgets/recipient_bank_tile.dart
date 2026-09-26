import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class RecipientBankTile extends StatelessWidget {
  final String selectedBank;
  final VoidCallback onTap;

  const RecipientBankTile({
    super.key,
    required this.selectedBank,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 12),
        child: Row(
          children: [
            Expanded(
              child: Text(
                selectedBank.isEmpty ? 'Select bank' : selectedBank,
                style: GoogleFonts.outfit(
                  fontSize: 14.5,
                  fontWeight:
                      selectedBank.isEmpty ? FontWeight.w400 : FontWeight.w500,
                  color: selectedBank.isEmpty
                      ? const Color(0xFF667085)
                      : const Color(0xFF101828),
                ),
              ),
            ),
            const Icon(
              Icons.chevron_right_rounded,
              color: Color(0xFF667085),
              size: 22,
            ),
          ],
        ),
      ),
    );
  }
}
