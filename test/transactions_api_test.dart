import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:novabanq/core/network/api_client.dart';
import 'package:novabanq/core/network/transactions_api.dart';

Map<String, dynamic> transaction({
  String id = 'tx-1',
  String direction = 'OUT',
  String type = 'TRANSFER',
  String? fromCurrency = 'NGN',
  String? toCurrency = 'GHS',
  int? fromMinor = 50000,
  int? toMinor = 42000,
  int fee = 100,
}) => {
  'transaction_id': id,
  'transaction_type': type,
  'direction': direction,
  'status': 'SETTLED',
  'counterparty': {'uid': 'other', 'tag': 'ada.gh', 'name': 'Ada'},
  'from_currency': fromCurrency,
  'to_currency': toCurrency,
  'from_amount_minor': fromMinor,
  'to_amount_minor': toMinor,
  'fee_minor': fee,
  'rate_scaled': 840000,
  'created_at': '2026-09-28T10:00:00Z',
};

void main() {
  test('list uses the documented limit and parses both directions', () async {
    final dio = Dio(BaseOptions(baseUrl: 'https://example.test/api/v1'));
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (request, handler) {
          expect(request.path, '/transactions');
          expect(request.queryParameters['limit'], 3);
          expect(request.headers['Authorization'], 'Bearer token');
          handler.resolve(
            Response(
              requestOptions: request,
              data: {
                'success': true,
                'data': {
                  'items': [
                    transaction(),
                    transaction(
                      id: 'tx-2',
                      direction: 'IN',
                      type: 'FUNDING',
                      fromCurrency: null,
                      fromMinor: null,
                      toCurrency: 'XOF',
                      toMinor: 57134,
                      fee: 0,
                    ),
                  ],
                  'next_cursor': 'opaque',
                },
              },
            ),
          );
        },
      ),
    );
    final api = TransactionsApi(
      ApiClient(dio: dio, tokenProvider: (_) async => 'token'),
    );
    final page = await api.getTransactions(limit: 3);
    expect(page.items.length, 2);
    expect(page.nextCursor, 'opaque');
    expect(page.items.first.displayAmount, '-₦500.00');
    expect(page.items.last.displayAmount, '+CFA57,134');
  });

  test('receipt reads the already-unwrapped single transaction', () async {
    final dio = Dio(BaseOptions(baseUrl: 'https://example.test/api/v1'));
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (request, handler) {
          expect(request.path, '/transactions/tx-1');
          handler.resolve(
            Response(
              requestOptions: request,
              data: {'success': true, 'data': transaction()},
            ),
          );
        },
      ),
    );
    final api = TransactionsApi(
      ApiClient(dio: dio, tokenProvider: (_) async => 'token'),
    );
    final receipt = await api.getTransaction('tx-1');
    expect(receipt.transactionId, 'tx-1');
    expect(receipt.status, 'SETTLED');
    expect(receipt.counterparty?.name, 'Ada');
  });

  test('receipt preserves scoped not-found errors', () async {
    final dio = Dio(BaseOptions(baseUrl: 'https://example.test/api/v1'));
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (request, handler) {
          handler.resolve(
            Response(
              requestOptions: request,
              statusCode: 404,
              data: {
                'success': false,
                'error': {
                  'code': 'TRANSACTION_NOT_FOUND',
                  'message': 'No transaction found with that id.',
                },
              },
            ),
          );
        },
      ),
    );
    final api = TransactionsApi(
      ApiClient(dio: dio, tokenProvider: (_) async => 'token'),
    );
    await expectLater(
      api.getTransaction('missing'),
      throwsA(
        isA<ApiFailure>().having(
          (failure) => failure.code,
          'code',
          'TRANSACTION_NOT_FOUND',
        ),
      ),
    );
  });
}
