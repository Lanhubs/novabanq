import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:novabanq/core/network/api_client.dart';
import 'package:novabanq/core/network/nova_api.dart';
import 'package:novabanq/features/home/models/nova_transfer.dart';

final quote = <String, dynamic>{
  'sender_currency': 'GHS',
  'recipient': {
    'uid': 'recipient-1',
    'tag': 'david.ng',
    'display_name': 'David',
    'country': 'NG',
    'currency': 'NGN',
  },
  'send_amount_minor': 500000,
  'fee_minor': 5000,
  'total_debit_minor': 505000,
  'receive_amount_minor': 57134100,
  'rate': '114.268226',
  'expires_at': '2099-09-28T15:03:25Z',
};

void main() {
  late Dio dio;
  late NovaApi api;
  setUp(() {
    dio = Dio(BaseOptions(baseUrl: 'https://example.test/api/v1'));
    api = NovaApi(ApiClient(dio: dio, tokenProvider: (_) async => 'token'));
  });

  test('ask uses authenticated envelope and renders backend answer', () async {
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (request, handler) {
          expect(request.path, '/ai/ask');
          expect(request.data, {'question': "what's my balance"});
          expect(request.headers['Authorization'], 'Bearer token');
          handler.resolve(
            Response(
              requestOptions: request,
              data: {
                'success': true,
                'data': {
                  'kind': 'BALANCE',
                  'answer': 'GHS 1,240.50',
                  'data': {'balance_minor': 124050, 'currency': 'GHS'},
                },
              },
            ),
          );
        },
      ),
    );
    final answer = await api.ask("what's my balance");
    expect(answer.kind, 'BALANCE');
    expect(answer.answer, 'GHS 1,240.50');
    expect(answer.data?['balance_minor'], 124050);
  });

  test(
    'preview keeps exact text, recipient uid, and schedule signal',
    () async {
      dio.interceptors.add(
        InterceptorsWrapper(
          onRequest: (request, handler) {
            expect(request.path, '/ai/parse-transfer');
            expect(request.data, {'text': 'send 5000 to david.ng at 5pm'});
            handler.resolve(
              Response(
                requestOptions: request,
                data: {
                  'success': true,
                  'data': {
                    'intent': {
                      'action': 'transfer',
                      'amount_major': '5000.00',
                      'recipient_tag': 'david.ng',
                      'execute_at': '2099-09-28T17:00:00Z',
                    },
                    'quote': quote,
                    'requested_text': 'send 5000 to david.ng at 5pm',
                  },
                },
              ),
            );
          },
        ),
      );
      final preview = await api.parseTransfer('send 5000 to david.ng at 5pm');
      expect(preview.isScheduled, isTrue);
      expect(preview.quote.recipient.uid, 'recipient-1');
      expect(preview.quote.totalDebitMinor, 505000);
    },
  );

  test(
    'execute sends confirmed uid and branches on scheduled result',
    () async {
      final preview = NovaTransferPreview(
        text: 'send 5000 to david.ng at 5pm',
        quote: NovaTransferPreview.fromJson({
          'intent': {'execute_at': '2099-09-28T17:00:00Z'},
          'quote': quote,
          'requested_text': 'send 5000 to david.ng at 5pm',
        }).quote,
        executeAt: DateTime.utc(2099, 9, 28, 17),
      );
      dio.interceptors.add(
        InterceptorsWrapper(
          onRequest: (request, handler) {
            expect(request.path, '/ai/execute-transfer');
            expect(request.data, {
              'text': preview.text,
              'pin': '12345',
              'confirmed_recipient_uid': 'recipient-1',
            });
            handler.resolve(
              Response(
                requestOptions: request,
                data: {
                  'success': true,
                  'data': {
                    'kind': 'SCHEDULED',
                    'scheduled_transfer': {
                      'scheduled_transfer_id': 'schedule-1',
                      'recipient_tag': 'david.ng',
                      'recipient_display_name': 'David',
                      'amount_minor': 500000,
                      'sender_currency': 'GHS',
                      'execute_at': '2099-09-28T17:00:00Z',
                      'status': 'PENDING',
                      'transaction_id': null,
                      'failure_reason': null,
                      'created_at': '2099-09-28T15:00:00Z',
                    },
                  },
                },
              ),
            );
          },
        ),
      );
      final result = await api.executeTransfer(preview: preview, pin: '12345');
      expect(result, isA<NovaScheduledTransfer>());
      expect((result as NovaScheduledTransfer).status, 'PENDING');
    },
  );

  test('immediate result parses the existing receipt model', () {
    final result = NovaTransferResult.fromJson({
      'kind': 'IMMEDIATE',
      'transfer': {
        'transaction_id': 'tx-1',
        'status': 'SETTLED',
        'quote': quote,
        'settled_at': '2099-09-28T15:03:12Z',
      },
    });
    expect(result, isA<NovaImmediateTransfer>());
    expect((result as NovaImmediateTransfer).transfer.transactionId, 'tx-1');
  });
}
