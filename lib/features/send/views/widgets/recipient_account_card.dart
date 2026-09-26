import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'recipient_account_field.dart';
import 'recipient_bank_tile.dart';
import 'recipient_tag_field.dart';

class RecipientAccountCard extends StatelessWidget {
  final TextEditingController accountController;
  final TextEditingController tagController;
  final String selectedBank;
  final VoidCallback onSelectBank;

  const RecipientAccountCard({
    super.key,
    required this.accountController,
    required this.tagController,
    required this.selectedBank,
    required this.onSelectBank,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFFF9FAFB),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 1. Header
          Text(
            'Recipient account',
            style: GoogleFonts.outfit(
              fontSize: 16.5,
              fontWeight: FontWeight.w700,
              color: const Color(0xFF101828),
            ),
          ),

          const SizedBox(height: 12),

          // 2. Account number field
          RecipientAccountField(controller: accountController),

          const Divider(color: Color(0xFFEAECF0), height: 1, thickness: 1),

          // 3. Bank selector tile
          RecipientBankTile(
            selectedBank: selectedBank,
            onTap: onSelectBank,
          ),

          const Divider(color: Color(0xFFEAECF0), height: 1, thickness: 1),

          // 4. Account tag field
          RecipientTagField(controller: tagController),
        ],
      ),
    );
  }
}
