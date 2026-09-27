import 'transfer_quote.dart';

class TransferResult {
  final String transactionId;
  final String status;
  final TransferQuote quote;
  final String settledAt;

  const TransferResult({
    required this.transactionId,
    required this.status,
    required this.quote,
    required this.settledAt,
  });

  factory TransferResult.fromJson(Map<String, dynamic> json) {
    return TransferResult(
      transactionId: json['transaction_id']?.toString() ?? '',
      status: json['status']?.toString() ?? 'SETTLED',
      quote: TransferQuote.fromJson(
        json['quote'] is Map<String, dynamic>
            ? json['quote'] as Map<String, dynamic>
            : const {},
      ),
      settledAt: json['settled_at']?.toString() ?? '',
    );
  }
}
