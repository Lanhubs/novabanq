part of 'send_amount_controller.dart';

extension SendAmountSheets on SendAmountController {
  void showConfirmTransactionSheet(TransferQuote q) {
    final sender = CurrencySymbols.symbolFor(q.senderCurrency);
    final receiver = CurrencySymbols.symbolFor(q.recipient.currency);
    Get.bottomSheet(
      ConfirmTransactionBottomSheet(
        recipientName: recipientName.value,
        fromAccount: '${q.senderCurrency} account',
        amountFromAccount:
            '$sender ${CurrencySymbols.formatMinor(q.totalDebitMinor, q.senderCurrency)}',
        amountToBeneficiary:
            '$receiver ${CurrencySymbols.formatMinor(q.receiveAmountMinor, q.recipient.currency)}',
        fee:
            '$sender ${CurrencySymbols.formatMinor(q.feeMinor, q.senderCurrency)}',
        onConfirm: () {
          Get.back();
          if (q.isExpired || quote.value != q) {
            TransferErrorHandler.showSnack(
              'Quote expired',
              'Refreshing quote...',
            );
            onContinue();
          } else {
            showPinBottomSheet(q);
          }
        },
      ),
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
    );
  }

  void showPinBottomSheet(TransferQuote q) {
    transactionPin.value = '';
    Get.bottomSheet(
      Obx(
        () => TransactionPinBottomSheet(
          pin: transactionPin.value,
          isLoading: isExecuting.value,
          onKeyPress: (d) {
            if (!isExecuting.value && transactionPin.value.length < 5) {
              transactionPin.value += d;
            }
          },
          onBackspace: () {
            if (!isExecuting.value && transactionPin.value.isNotEmpty) {
              transactionPin.value = transactionPin.value.substring(
                0,
                transactionPin.value.length - 1,
              );
            }
          },
          onClear: () {
            if (!isExecuting.value) transactionPin.value = '';
          },
          onConfirm: () => _executeTransfer(q),
        ),
      ),
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
    );
  }
}
