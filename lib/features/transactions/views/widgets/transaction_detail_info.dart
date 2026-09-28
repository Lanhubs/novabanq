import 'package:flutter/material.dart';
import 'package:novabanq/core/utils/currency_symbols.dart';
import 'package:novabanq/features/send/models/transaction_summary.dart';
import 'info_row.dart';
import 'section_title.dart';

class TransactionDetailInfo extends StatelessWidget {
  final TransactionSummary transaction;
  final VoidCallback onCopyId;

  const TransactionDetailInfo({
    super.key,
    required this.transaction,
    required this.onCopyId,
  });

  String _money(int? minor, String? currency) {
    if (minor == null || currency == null) return '—';
    return '${CurrencySymbols.symbolFor(currency)}${CurrencySymbols.formatMinor(minor, currency)}';
  }

  @override
  Widget build(BuildContext context) {
    final t = transaction;
    final local = t.createdAt.toLocal();
    final time =
        '${local.hour.toString().padLeft(2, '0')}:${local.minute.toString().padLeft(2, '0')}';
    final party = t.counterparty;
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFFF9FAFB),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFE4E7EC)),
      ),
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SectionTitle(title: 'Transaction Information'),
          const SizedBox(height: 16),
          InfoRow('Transaction ID', t.transactionId, onCopy: onCopyId),
          const Divider(color: Color(0xFFE4E7EC)),
          InfoRow('Type', t.transactionType.toLowerCase()),
          const Divider(color: Color(0xFFE4E7EC)),
          InfoRow('Direction', t.isIncoming ? 'Incoming' : 'Outgoing'),
          const Divider(color: Color(0xFFE4E7EC)),
          InfoRow('Date', '${t.dateLabel} at $time'),
          if (party != null) ...[
            const SizedBox(height: 24),
            const SectionTitle(title: 'Counterparty'),
            const SizedBox(height: 16),
            InfoRow(
              'Name',
              party.name?.isNotEmpty == true ? party.name! : party.uid,
            ),
            if (party.tag?.isNotEmpty == true)
              InfoRow('Tag', '@${party.tag!.replaceFirst('@', '')}'),
          ],
          const SizedBox(height: 24),
          const SectionTitle(title: 'Amount Details'),
          const SizedBox(height: 16),
          if (t.fromAmountMinor != null)
            InfoRow(
              'Sent',
              _money(t.fromAmountMinor, t.fromCurrency),
              highlight: !t.isIncoming,
            ),
          if (t.toAmountMinor != null)
            InfoRow(
              'Received',
              _money(t.toAmountMinor, t.toCurrency),
              highlight: t.isIncoming,
              incoming: t.isIncoming,
            ),
          if (t.feeMinor > 0)
            InfoRow('Fee', _money(t.feeMinor, t.fromCurrency)),
          if (!t.isIncoming && t.fromAmountMinor != null)
            InfoRow(
              'Total debited',
              _money(t.fromAmountMinor! + t.feeMinor, t.fromCurrency),
            ),
          if (t.rateScaled != null)
            InfoRow(
              'Rate',
              '${t.rateScaled! ~/ 1000000}.${(t.rateScaled! % 1000000).toString().padLeft(6, '0')}',
            ),
        ],
      ),
    );
  }
}
