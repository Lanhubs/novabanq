import 'package:flutter/foundation.dart';
import 'package:novabanq/core/network/api_client.dart';
import 'package:novabanq/core/network/nova_api.dart';
import 'package:novabanq/features/home/models/nova_transfer.dart';

enum NovaInputMode { ask, transfer, schedule }

class NovaMessage {
  const NovaMessage(this.text, {this.isUser = false, this.isError = false});
  final String text;
  final bool isUser;
  final bool isError;
}

class NovaConversationController extends ChangeNotifier {
  NovaConversationController(this.api);
  final NovaApi api;

  final messages = <NovaMessage>[];
  NovaInputMode mode = NovaInputMode.ask;
  bool isBusy = false;
  bool _disposed = false;

  void selectMode(NovaInputMode next) {
    if (isBusy) return;
    mode = mode == next ? NovaInputMode.ask : next;
    if (mode != NovaInputMode.ask) {
      messages.add(
        NovaMessage(
          mode == NovaInputMode.schedule
              ? 'Tell me the amount, recipient @tag, and when to schedule it.'
              : 'Tell me the amount and recipient @tag. I’ll show you a quote first.',
        ),
      );
    }
    notifyListeners();
  }

  Future<NovaTransferPreview?> submit(String raw) async {
    final text = raw.trim();
    if (isBusy || text.isEmpty) return null;
    if (text.length > 500) {
      messages.add(
        const NovaMessage(
          'Keep your message under 500 characters.',
          isError: true,
        ),
      );
      notifyListeners();
      return null;
    }
    messages.add(NovaMessage(text, isUser: true));
    isBusy = true;
    notifyListeners();
    try {
      if (mode == NovaInputMode.ask) {
        final answer = await api.ask(text);
        messages.add(NovaMessage(answer.answer));
        return null;
      }
      final preview = await api.parseTransfer(text);
      if (mode == NovaInputMode.schedule && !preview.isScheduled) {
        messages.add(
          const NovaMessage(
            'Include a future time to schedule this payment. No transfer was made.',
            isError: true,
          ),
        );
        return null;
      }
      final quote = preview.quote;
      if (quote.isExpired ||
          quote.recipient.uid.isEmpty ||
          quote.recipient.tag.isEmpty ||
          quote.recipient.currency.isEmpty ||
          quote.senderCurrency.isEmpty ||
          quote.sendAmountMinor <= 0 ||
          quote.receiveAmountMinor <= 0 ||
          quote.totalDebitMinor < quote.sendAmountMinor) {
        throw const ApiFailure(
          'INVALID_QUOTE',
          'The quote is unavailable. Please try again.',
        );
      }
      messages.add(
        NovaMessage(
          preview.isScheduled
              ? 'I found the recipient and a quote. Review the scheduled payment before confirming.'
              : 'I found the recipient and a quote. Review it before confirming.',
        ),
      );
      return preview;
    } on ApiFailure catch (error) {
      messages.add(NovaMessage(_errorText(error), isError: true));
    } catch (_) {
      messages.add(
        const NovaMessage(
          'Nova could not complete that request. Try again.',
          isError: true,
        ),
      );
    } finally {
      isBusy = false;
      if (!_disposed) notifyListeners();
    }
    return null;
  }

  void report(String text, {bool isError = false}) {
    if (_disposed) return;
    messages.add(NovaMessage(text, isError: isError));
    notifyListeners();
  }

  String _errorText(ApiFailure error) {
    if (error.status != null && error.status! >= 500) {
      return 'Nova is unavailable right now — try again in a moment.';
    }
    if (error.code == 'NETWORK_ERROR') {
      return 'Check your connection and try again.';
    }
    if (error.status == 422 && error.code == 'VALIDATION_ERROR') {
      final fields = error.details['fields'];
      if (fields == null ||
          (fields is Map && fields.isEmpty) ||
          (fields is List && fields.isEmpty)) {
        return error.message;
      }
    }
    return error.message;
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}
