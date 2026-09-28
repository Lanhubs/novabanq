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

  Future<NovaTransferPreview?> submit(
    String raw, {
    DateTime? scheduleAt,
  }) async {
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
    final requestText = scheduleAt == null
        ? text
        : '$text at ${_scheduleTimestamp(scheduleAt)}';
    messages.add(
      NovaMessage(
        scheduleAt == null
            ? text
            : 'Schedule for ${_scheduleLabel(scheduleAt)}',
        isUser: true,
      ),
    );
    isBusy = true;
    notifyListeners();
    try {
      if (mode == NovaInputMode.ask) {
        final answer = await api.ask(text);
        messages.add(NovaMessage(answer.answer));
        return null;
      }
      final preview = await api.parseTransfer(requestText);
      if (mode == NovaInputMode.schedule && !preview.isScheduled) {
        if (scheduleAt != null) {
          messages.add(
            const NovaMessage(
              'I could not confirm that date and time. Choose another future time.',
              isError: true,
            ),
          );
          return null;
        }
        messages.add(
          const NovaMessage('Choose a future date and time for this payment.'),
        );
        return preview;
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

  String _scheduleTimestamp(DateTime dateTime) {
    final local = dateTime.toLocal();
    final offset = local.timeZoneOffset;
    final sign = offset.isNegative ? '-' : '+';
    final offsetHours = offset.inHours.abs().toString().padLeft(2, '0');
    final offsetMinutes = (offset.inMinutes.abs() % 60).toString().padLeft(
      2,
      '0',
    );
    return '${local.year.toString().padLeft(4, '0')}-'
        '${local.month.toString().padLeft(2, '0')}-'
        '${local.day.toString().padLeft(2, '0')}T'
        '${local.hour.toString().padLeft(2, '0')}:'
        '${local.minute.toString().padLeft(2, '0')}:00'
        '$sign$offsetHours:$offsetMinutes';
  }

  String _scheduleLabel(DateTime dateTime) {
    const months = [
      'Jan',
      'Feb',
      'Mar',
      'Apr',
      'May',
      'Jun',
      'Jul',
      'Aug',
      'Sep',
      'Oct',
      'Nov',
      'Dec',
    ];
    final local = dateTime.toLocal();
    final hour = local.hour % 12 == 0 ? 12 : local.hour % 12;
    final minute = local.minute.toString().padLeft(2, '0');
    final period = local.hour < 12 ? 'AM' : 'PM';
    return '${months[local.month - 1]} ${local.day}, ${local.year} '
        'at $hour:$minute $period';
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
