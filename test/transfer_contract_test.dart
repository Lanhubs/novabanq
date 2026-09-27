import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:novabanq/core/network/api_client.dart';
import 'package:novabanq/core/network/transfer_api.dart';
import 'package:novabanq/core/utils/currency_symbols.dart';
import 'package:novabanq/features/send/models/transfer_quote.dart';

void main() {
  test('money entry uses exact minor units and XOF has no fractional unit', () {
    expect(CurrencySymbols.parseMinor('2,400.05', 'NGN'), 240005);
    expect(CurrencySymbols.parseMinor('100', 'XOF'), 100);
    expect(CurrencySymbols.parseMinor('100.50', 'XOF'), isNull);
    expect(CurrencySymbols.parseMinor('1.005', 'NGN'), isNull);
  });

  test('malformed or expired quote cannot be confirmed', () {
    final quote = TransferQuote.fromJson({
      'sender_currency': 'NGN',
      'recipient': {'tag': 'ada.gh', 'currency': 'GHS'},
      'send_amount_minor': 100,
      'fee_minor': 10,
      'total_debit_minor': 110,
      'receive_amount_minor': 1,
      'expires_at': 'invalid',
    });
    expect(quote.isExpired, isTrue);
  });

  test(
    'transfer sends documented fields with a Firebase bearer token',
    () async {
      final dio = Dio(BaseOptions(baseUrl: 'https://example.test/api/v1'));
      final requests = <RequestOptions>[];
      dio.interceptors.add(
        InterceptorsWrapper(
          onRequest: (request, handler) {
            requests.add(request);
            handler.resolve(
              Response(
                requestOptions: request,
                statusCode: 201,
                data: {
                  'success': true,
                  'data': {
                    'transaction_id': 'tx-123',
                    'status': 'SETTLED',
                    'settled_at': '2026-09-27T00:00:00Z',
                    'quote': {
                      'sender_currency': 'NGN',
                      'recipient': {'tag': 'ada.gh', 'currency': 'GHS'},
                      'send_amount_minor': 240000,
                      'fee_minor': 100,
                      'total_debit_minor': 240100,
                      'receive_amount_minor': 15000,
                      'rate': '0.0625',
                      'expires_at': '2026-09-27T00:01:00Z',
                    },
                  },
                },
              ),
            );
          },
        ),
      );
      final api = TransferApi(
        ApiClient(dio: dio, tokenProvider: (_) async => 'firebase-token'),
      );
      final result = await api.executeTransfer(
        recipientTag: 'ada.gh',
        amountMinor: 240000,
        idempotencyKey: '12345678-1234-4123-8123-123456789012',
        pin: '12345',
      );
      expect(result.transactionId, 'tx-123');
      expect(result.quote.totalDebitMinor, 240100);
      expect(requests.single.path, '/transfers');
      expect(requests.single.headers['Authorization'], 'Bearer firebase-token');
      expect(requests.single.data, {
        'recipient_tag': 'ada.gh',
        'amount_minor': 240000,
        'idempotency_key': '12345678-1234-4123-8123-123456789012',
        'pin': '12345',
      });
    },
  );
}
