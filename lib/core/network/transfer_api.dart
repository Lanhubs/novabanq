import 'package:novabanq/features/send/models/transfer_quote.dart';
import 'package:novabanq/features/send/models/transfer_result.dart';
import 'package:novabanq/features/send/models/user_account_balance.dart';
import 'api_client.dart';

class TransferApi {
  final ApiClient client;

  TransferApi(this.client);

  Future<UserAccountBalance> getAccount() async {
    final data = await client.request('GET', '/accounts/me');
    return UserAccountBalance.fromJson(data);
  }

  Future<TransferQuote> getQuote({
    required String recipientTag,
    required int amountMinor,
  }) async {
    final data = await client.request(
      'POST',
      '/transfers/quote',
      body: {
        'recipient_tag': recipientTag,
        'amount_minor': amountMinor,
      },
    );
    return TransferQuote.fromJson(data);
  }

  Future<TransferResult> executeTransfer({
    required String recipientTag,
    required int amountMinor,
    required String idempotencyKey,
    required String pin,
  }) async {
    final data = await client.request(
      'POST',
      '/transfers',
      body: {
        'recipient_tag': recipientTag,
        'amount_minor': amountMinor,
        'idempotency_key': idempotencyKey,
        'pin': pin,
      },
    );
    return TransferResult.fromJson(data);
  }
}
