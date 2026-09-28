import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:novabanq/core/network/api_client.dart';
import 'package:novabanq/core/network/nova_api.dart';
import 'package:novabanq/features/home/controllers/nova_conversation_controller.dart';

void main() {
  test(
    'schedule without a time requests one before returning a preview',
    () async {
      final dio = Dio(BaseOptions(baseUrl: 'https://example.test/api/v1'));
      final requests = <String>[];
      dio.interceptors.add(
        InterceptorsWrapper(
          onRequest: (request, handler) {
            requests.add(
              (request.data as Map<String, dynamic>)['text'] as String,
            );
            final hasSchedule = requests.length == 2;
            handler.resolve(
              Response(
                requestOptions: request,
                data: {
                  'success': true,
                  'data': {
                    'intent': {
                      'execute_at': hasSchedule ? '2099-09-28T17:00:00Z' : null,
                    },
                    'quote': {
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
                    },
                    'requested_text': requests.last,
                  },
                },
              ),
            );
          },
        ),
      );
      final api = NovaApi(
        ApiClient(dio: dio, tokenProvider: (_) async => 'token'),
      );
      final conversation = NovaConversationController(api);
      conversation.selectMode(NovaInputMode.schedule);

      final incomplete = await conversation.submit('send 5000 to david.ng');
      expect(incomplete, isNotNull);
      expect(incomplete!.isScheduled, isFalse);
      expect(conversation.messages.last.text, contains('Choose a future date'));

      final scheduled = await conversation.submit(
        'send 5000 to david.ng',
        scheduleAt: DateTime(2099, 9, 28, 17),
      );
      expect(scheduled?.isScheduled, isTrue);
      expect(requests.first, 'send 5000 to david.ng');
      expect(
        requests.last,
        startsWith('send 5000 to david.ng at 2099-09-28T17:00:00'),
      );

      conversation.dispose();
    },
  );
}
