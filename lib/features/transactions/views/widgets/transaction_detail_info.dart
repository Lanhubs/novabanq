import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/features/send/models/transaction_summary.dart';
import 'info_row.dart';

class TransactionDetailInfo extends StatelessWidget {
  final TransactionSummary transaction;
  final VoidCallback onCopyId;

  const TransactionDetailInfo({
    super.key,
    required this.transaction,
    required this.onCopyId,
  });

  @override
  Widget build(BuildContext context) {
    final t = transaction;
    final local = t.createdAt.toLocal();
    final status = switch (t.status.toUpperCase()) {
      'SETTLED' || 'COMPLETED' || 'SUCCESS' => 'Completed',
      'PENDING' => 'Pending',
      'FAILED' => 'Failed',
      'CANCELLED' => 'Cancelled',
      _ => t.status.replaceAll('_', ' '),
    };
    final statusColor = switch (t.status.toUpperCase()) {
      'SETTLED' || 'COMPLETED' || 'SUCCESS' => const Color(0xFF067647),
      'PENDING' => const Color(0xFFB54708),
      'FAILED' || 'CANCELLED' => const Color(0xFFB42318),
      _ => const Color(0xFF344054),
    };
    final type = t.transactionType
        .replaceAll('_', ' ')
        .split(' ')
        .where((word) => word.isNotEmpty)
        .map(
          (word) =>
              '${word[0].toUpperCase()}${word.substring(1).toLowerCase()}',
        )
        .join(' ');
    final time =
        '${local.hour.toString().padLeft(2, '0')}:${local.minute.toString().padLeft(2, '0')}';
    final party = t.counterparty;
    final partyName = party?.name?.isNotEmpty == true
        ? party!.name!
        : party?.tag?.isNotEmpty == true
        ? '@${party!.tag!.replaceFirst('@', '')}'
        : party?.uid;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Transaction details',
          style: GoogleFonts.outfit(
            fontSize: 15,
            fontWeight: FontWeight.w600,
            color: const Color(0xFF101828),
          ),
        ),
        const SizedBox(height: 8),
        InfoRow('Status', status, valueColor: statusColor),
        const Divider(height: 1, color: Color(0xFFEAECF0)),
        InfoRow('Transaction type', type.isEmpty ? '—' : type),
        if (partyName?.isNotEmpty == true) ...[
          const Divider(height: 1, color: Color(0xFFEAECF0)),
          InfoRow(t.isIncoming ? 'From' : 'To', partyName!),
        ],
        const Divider(height: 1, color: Color(0xFFEAECF0)),
        InfoRow('Date / time', '${t.dateLabel} at $time'),
        const Divider(height: 1, color: Color(0xFFEAECF0)),
        InfoRow('Transaction ID', t.transactionId, onCopy: onCopyId),
      ],
    );
  }
}
