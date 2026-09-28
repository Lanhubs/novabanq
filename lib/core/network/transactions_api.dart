import 'package:novabanq/features/send/models/transaction_page.dart';
import 'package:novabanq/features/send/models/transaction_summary.dart';
import 'api_client.dart';

class TransactionsApi {
  final ApiClient client;

  TransactionsApi(this.client);

  Future<TransactionPage> getTransactions({int limit = 20}) async {
    if (limit < 1 || limit > 100) {
      throw ArgumentError.value(limit, 'limit', 'Must be between 1 and 100');
    }
    final data = await client.request(
      'GET',
      '/transactions',
      query: {'limit': limit},
    );

    return TransactionPage.fromJson(data);
  }

  Future<TransactionSummary> getTransaction(String transactionId) async {
    if (transactionId.isEmpty) {
      throw ArgumentError.value(transactionId, 'transactionId');
    }
    final data = await client.request(
      'GET',
      '/transactions/${Uri.encodeComponent(transactionId)}',
    );
    return TransactionSummary.fromJson(data);
  }
}
