import 'transaction_summary.dart';

class TransactionPage {
  final List<TransactionSummary> items;
  final String? nextCursor;

  const TransactionPage({required this.items, required this.nextCursor});

  factory TransactionPage.fromJson(Map<String, dynamic> json) {
    final raw = json['items'];
    if (raw is! List) throw const FormatException('Invalid transaction list');
    return TransactionPage(
      items: raw
          .map((item) {
            if (item is! Map<String, dynamic>) {
              throw const FormatException('Invalid transaction item');
            }
            return TransactionSummary.fromJson(item);
          })
          .toList(growable: false),
      nextCursor: json['next_cursor']?.toString(),
    );
  }
}
