import 'package:novabanq/features/send/models/transfer_quote.dart';
import 'package:novabanq/features/send/models/transfer_result.dart';

class NovaTransferPreview {
  const NovaTransferPreview({
    required this.text,
    required this.quote,
    required this.executeAt,
  });

  final String text;
  final TransferQuote quote;
  final DateTime? executeAt;

  bool get isScheduled => executeAt != null;

  factory NovaTransferPreview.fromJson(Map<String, dynamic> json) {
    final intent = json['intent'] as Map<String, dynamic>;
    final executeAt = intent['execute_at'] as String?;
    return NovaTransferPreview(
      text: json['requested_text'] as String,
      quote: TransferQuote.fromJson(json['quote'] as Map<String, dynamic>),
      executeAt: executeAt == null ? null : DateTime.parse(executeAt),
    );
  }
}

sealed class NovaTransferResult {
  const NovaTransferResult();

  factory NovaTransferResult.fromJson(Map<String, dynamic> json) {
    return switch (json['kind']) {
      'IMMEDIATE' => NovaImmediateTransfer(
        TransferResult.fromJson(json['transfer'] as Map<String, dynamic>),
      ),
      'SCHEDULED' => NovaScheduledTransfer.fromJson(
        json['scheduled_transfer'] as Map<String, dynamic>,
      ),
      _ => throw FormatException('Unknown AI transfer kind: ${json['kind']}'),
    };
  }
}

class NovaImmediateTransfer extends NovaTransferResult {
  const NovaImmediateTransfer(this.transfer);
  final TransferResult transfer;
}

class NovaScheduledTransfer extends NovaTransferResult {
  const NovaScheduledTransfer({
    required this.id,
    required this.recipientTag,
    required this.recipientName,
    required this.amountMinor,
    required this.currency,
    required this.executeAt,
    required this.status,
  });

  final String id;
  final String recipientTag;
  final String? recipientName;
  final int amountMinor;
  final String currency;
  final DateTime executeAt;
  final String status;

  factory NovaScheduledTransfer.fromJson(Map<String, dynamic> json) {
    return NovaScheduledTransfer(
      id: json['scheduled_transfer_id'] as String,
      recipientTag: json['recipient_tag'] as String,
      recipientName: json['recipient_display_name'] as String?,
      amountMinor: json['amount_minor'] as int,
      currency: json['sender_currency'] as String,
      executeAt: DateTime.parse(json['execute_at'] as String),
      status: json['status'] as String,
    );
  }
}
