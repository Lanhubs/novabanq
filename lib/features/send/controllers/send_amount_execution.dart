part of 'send_amount_controller.dart';

extension SendAmountExecution on SendAmountController {
  Future<void> _executeTransfer(TransferQuote q) async {
    if (isExecuting.value) return;
    if (transactionPin.value.length != 5) {
      TransferErrorHandler.showSnack(
        'Enter PIN',
        'Please enter your 5-digit PIN.',
      );
      return;
    }
    if (q.isExpired) {
      Get.back();
      TransferErrorHandler.showSnack('Quote expired', 'Refreshing quote...');
      await onContinue();
      return;
    }
    final fingerprint = '${q.recipient.tag}:${q.sendAmountMinor}';
    final pin = transactionPin.value;
    try {
      isExecuting.value = true;
      if (_attemptFingerprint != fingerprint) {
        _idempotencyKey = await TransferAttemptStore.read(fingerprint);
        _attemptFingerprint = fingerprint;
      }
      _idempotencyKey ??= Idempotency.generateKey();
      await TransferAttemptStore.write(fingerprint, _idempotencyKey!);
      final result = await _sendWithRetry(q, pin);
      await TransferAttemptStore.clear(fingerprint);
      _idempotencyKey = null;
      transactionPin.value = '';
      if (Get.isRegistered<HomeController>()) {
        Get.find<HomeController>().loadAccount();
      }
      Get.back();
      Get.off(
        () => const TransferSuccessScreen(),
        binding: TransferSuccessBinding(),
        arguments: result,
      );
    } on ApiFailure catch (e) {
      if (!_isRetryable(e)) {
        await TransferAttemptStore.clear(fingerprint);
        _idempotencyKey = null;
        _attemptFingerprint = null;
      }
      transactionPin.value = '';
      if (e.code == 'PIN_LOCKED' ||
          e.code == 'INSUFFICIENT_BALANCE' ||
          e.code == 'DUPLICATE_TRANSFER') {
        Get.back();
      }
      TransferErrorHandler.handleExecuteError(e);
    } catch (_) {
      transactionPin.value = '';
      TransferErrorHandler.showSnack(
        'Connection uncertain',
        'The transfer may still be processing. Retry with the same details.',
      );
    } finally {
      isExecuting.value = false;
    }
  }

  bool _isRetryable(ApiFailure e) =>
      e.code == 'NETWORK_ERROR' || e.status == 500 || e.status == 502;

  Future<TransferResult> _sendWithRetry(TransferQuote q, String pin) async {
    for (var attempt = 0; ; attempt++) {
      try {
        return await api.executeTransfer(
          recipientTag: q.recipient.tag,
          amountMinor: q.sendAmountMinor,
          idempotencyKey: _idempotencyKey!,
          pin: pin,
        );
      } on ApiFailure catch (e) {
        if (!_isRetryable(e) || attempt >= 2) rethrow;
        await Future<void>.delayed(Duration(milliseconds: 250 * (attempt + 1)));
      }
    }
  }
}
