import 'transfer_recipient.dart';

class TransferQuote {
  final String senderCurrency;
  final TransferRecipient recipient;
  final int sendAmountMinor;
  final int feeMinor;
  final int totalDebitMinor;
  final int receiveAmountMinor;
  final String rate;
  final String expiresAt;

  const TransferQuote({
    required this.senderCurrency,
    required this.recipient,
    required this.sendAmountMinor,
    required this.feeMinor,
    required this.totalDebitMinor,
    required this.receiveAmountMinor,
    required this.rate,
    required this.expiresAt,
  });

  bool get isExpired {
    try {
      return DateTime.now().toUtc().isAfter(DateTime.parse(expiresAt).toUtc());
    } catch (_) {
      return true;
    }
  }

  factory TransferQuote.fromJson(Map<String, dynamic> json) {
    return TransferQuote(
      senderCurrency: json['sender_currency']?.toString() ?? '',
      recipient: TransferRecipient.fromJson(
        json['recipient'] is Map<String, dynamic>
            ? json['recipient'] as Map<String, dynamic>
            : const {},
      ),
      sendAmountMinor: (json['send_amount_minor'] as num?)?.toInt() ?? 0,
      feeMinor: (json['fee_minor'] as num?)?.toInt() ?? 0,
      totalDebitMinor: (json['total_debit_minor'] as num?)?.toInt() ?? 0,
      receiveAmountMinor: (json['receive_amount_minor'] as num?)?.toInt() ?? 0,
      rate: json['rate']?.toString() ?? '1.0',
      expiresAt: json['expires_at']?.toString() ?? '',
    );
  }
}
