import 'package:novabanq/core/utils/currency_symbols.dart';

class TransactionParty {
  final String uid;
  final String? tag;
  final String? name;

  const TransactionParty({required this.uid, this.tag, this.name});

  factory TransactionParty.fromJson(Map<String, dynamic> json) {
    return TransactionParty(
      uid: json['uid']?.toString() ?? '',
      tag: json['tag']?.toString(),
      name: json['name']?.toString(),
    );
  }
}

class TransactionSummary {
  final String transactionId;
  final String transactionType;
  final String direction;
  final String status;
  final TransactionParty? counterparty;
  final String? fromCurrency;
  final String? toCurrency;
  final int? fromAmountMinor;
  final int? toAmountMinor;
  final int feeMinor;
  final int? rateScaled;
  final DateTime createdAt;

  const TransactionSummary({
    required this.transactionId,
    required this.transactionType,
    required this.direction,
    required this.status,
    required this.counterparty,
    required this.fromCurrency,
    required this.toCurrency,
    required this.fromAmountMinor,
    required this.toAmountMinor,
    required this.feeMinor,
    required this.rateScaled,
    required this.createdAt,
  });

  factory TransactionSummary.fromJson(Map<String, dynamic> json) {
    final id = json['transaction_id']?.toString() ?? '';
    final date = DateTime.tryParse(json['created_at']?.toString() ?? '');
    if (id.isEmpty || date == null) {
      throw const FormatException('Invalid transaction');
    }
    final party = json['counterparty'];
    return TransactionSummary(
      transactionId: id,
      transactionType: json['transaction_type']?.toString() ?? '',
      direction: json['direction']?.toString() ?? '',
      status: json['status']?.toString() ?? '',
      counterparty: party is Map<String, dynamic>
          ? TransactionParty.fromJson(party)
          : null,
      fromCurrency: json['from_currency']?.toString(),
      toCurrency: json['to_currency']?.toString(),
      fromAmountMinor: (json['from_amount_minor'] as num?)?.toInt(),
      toAmountMinor: (json['to_amount_minor'] as num?)?.toInt(),
      feeMinor: (json['fee_minor'] as num?)?.toInt() ?? 0,
      rateScaled: (json['rate_scaled'] as num?)?.toInt(),
      createdAt: date,
    );
  }

  bool get isIncoming => direction == 'IN';
  String get title {
    if (transactionType == 'FUNDING') return 'Account funding';
    if (transactionType == 'WITHDRAWAL') return 'Withdrawal';
    if (transactionType == 'REVERSAL') return 'Reversal';
    final party = counterparty;
    return party?.name?.isNotEmpty == true
        ? party!.name!
        : party?.tag?.isNotEmpty == true
        ? '@${party!.tag}'
        : party?.uid.isNotEmpty == true
        ? party!.uid
        : 'Transfer';
  }

  String get subtitle {
    final tag = counterparty?.tag;
    return tag == null || tag.isEmpty
        ? transactionType.toLowerCase()
        : '@${tag.replaceFirst('@', '')}';
  }

  String get displayAmount {
    final currency = isIncoming ? toCurrency : fromCurrency;
    final minor = isIncoming ? toAmountMinor : fromAmountMinor;
    if (currency == null || minor == null) return '—';
    final symbol = CurrencySymbols.symbolFor(currency);
    return '${isIncoming ? '+' : '-'}$symbol${CurrencySymbols.formatMinor(minor, currency)}';
  }

  String get dateLabel {
    final local = createdAt.toLocal();
    final day = local.day.toString().padLeft(2, '0');
    final month = local.month.toString().padLeft(2, '0');
    return '$day-$month-${local.year}';
  }
}
