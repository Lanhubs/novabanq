import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'transfer_detail_row.dart';

class TransferDetailsSection extends StatelessWidget {
  final String status;
  final String accountName;
  final String accountNumber;
  final String dateTime;
  final String transactionId;
  final VoidCallback onCopyTransactionId;

  const TransferDetailsSection({
    super.key,
    required this.status,
    required this.accountName,
    required this.accountNumber,
    required this.dateTime,
    required this.transactionId,
    required this.onCopyTransactionId,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Transactions details',
          style: GoogleFonts.outfit(
            fontSize: 16,
            fontWeight: FontWeight.w700,
            color: const Color(0xFF101828),
          ),
        ),
        const SizedBox(height: 10),
        TransferDetailRow(
          label: 'Status',
          value: status,
          valueColor: const Color(0xFF22C55E),
        ),
        TransferDetailRow(
          label: 'Account name',
          value: accountName,
        ),
        TransferDetailRow(
          label: 'Account number',
          value: accountNumber,
        ),
        TransferDetailRow(
          label: 'Date/Time',
          value: dateTime,
        ),
        TransferDetailRow(
          label: 'Transaction ID',
          value: transactionId,
          showCopyIcon: true,
          onCopy: onCopyTransactionId,
        ),
      ],
    );
  }
}
