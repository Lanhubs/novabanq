import 'package:novabanq/features/home/models/nova_answer.dart';
import 'package:novabanq/features/home/models/nova_transfer.dart';
import 'api_client.dart';

class NovaApi {
  const NovaApi(this.client);

  final ApiClient client;

  Future<NovaAnswer> ask(String question) async {
    final data = await client.request(
      'POST',
      '/ai/ask',
      body: {'question': question},
    );
    return NovaAnswer.fromJson(data);
  }

  Future<NovaTransferPreview> parseTransfer(String text) async {
    final data = await client.request(
      'POST',
      '/ai/parse-transfer',
      body: {'text': text},
    );
    return NovaTransferPreview.fromJson(data);
  }

  Future<NovaTransferResult> executeTransfer({
    required NovaTransferPreview preview,
    required String pin,
  }) async {
    final data = await client.request(
      'POST',
      '/ai/execute-transfer',
      body: {
        'text': preview.text,
        'pin': pin,
        'confirmed_recipient_uid': preview.quote.recipient.uid,
      },
    );
    return NovaTransferResult.fromJson(data);
  }
}
