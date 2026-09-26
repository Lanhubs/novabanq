import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/core/widgets/sheet_drag_handle.dart';
import 'package:novabanq/features/auth/views/widgets/auth_cta_button.dart';
import 'transaction_detail_row.dart';

class ConfirmTransactionBottomSheet extends StatelessWidget {
  final String recipientName;
  final String fromAccount;
  final String amountFromAccount;
  final String amountToBeneficiary;
  final VoidCallback onConfirm;

  const ConfirmTransactionBottomSheet({
    super.key,
    required this.recipientName,
    required this.fromAccount,
    required this.amountFromAccount,
    required this.amountToBeneficiary,
    required this.onConfirm,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const SheetDragHandle(),
              const SizedBox(height: 12),

              // Title
              Text(
                'Confirm transaction',
                style: GoogleFonts.outfit(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  color: const Color(0xFF101828),
                ),
              ),

              const SizedBox(height: 6),

              // Subtitle
              Text(
                'Carefully confirm your transaction before\nsending',
                textAlign: TextAlign.center,
                style: GoogleFonts.outfit(
                  fontSize: 13,
                  fontWeight: FontWeight.w400,
                  color: const Color(0xFF667085),
                  height: 1.4,
                ),
              ),

              const SizedBox(height: 24),

              // Detail Rows
              TransactionDetailRow(
                label: 'To',
                value: recipientName,
              ),
              TransactionDetailRow(
                label: 'From',
                value: fromAccount,
              ),
              TransactionDetailRow(
                label: 'Amount from account',
                value: '₦ $amountFromAccount',
              ),
              TransactionDetailRow(
                label: 'Amount to beneficiary',
                value: '₵ $amountToBeneficiary',
              ),

              const SizedBox(height: 28),

              // Confirm CTA Button
              AuthCtaButton(
                text: 'Confirm',
                onPressed: onConfirm,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
