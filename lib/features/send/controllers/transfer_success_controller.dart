import 'package:flutter/services.dart';
import 'package:get/get.dart';
import 'package:novabanq/app/routes/app_routes.dart';
import 'package:novabanq/core/utils/helpers.dart';
import 'package:novabanq/features/send/models/transfer_result.dart';
import 'package:novabanq/core/utils/currency_symbols.dart';

class TransferSuccessController extends GetxController {
  final status = 'Pending'.obs;
  final accountName = '—'.obs;
  final accountNumber = '—'.obs;
  final dateTime = '—'.obs;
  final transactionId = '—'.obs;
  final amountSent = '—'.obs;
  final amountReceived = '—'.obs;
  final fee = '—'.obs;

  @override
  void onInit() {
    super.onInit();
    final args = Get.arguments;
    if (args is TransferResult) {
      status.value = args.status == 'SETTLED' ? 'Completed' : args.status;
      if (args.quote.recipient.displayName.isNotEmpty) {
        accountName.value = args.quote.recipient.displayName;
      }
      if (args.quote.recipient.tag.isNotEmpty) {
        accountNumber.value = '@${args.quote.recipient.tag}';
      }
      if (args.transactionId.isNotEmpty) {
        transactionId.value = args.transactionId;
      }
      if (args.settledAt.isNotEmpty) {
        dateTime.value = _formatIso(args.settledAt);
      }
      final q = args.quote;
      amountSent.value =
          '${CurrencySymbols.symbolFor(q.senderCurrency)} ${CurrencySymbols.formatMinor(q.totalDebitMinor, q.senderCurrency)}';
      amountReceived.value =
          '${CurrencySymbols.symbolFor(q.recipient.currency)} ${CurrencySymbols.formatMinor(q.receiveAmountMinor, q.recipient.currency)}';
      fee.value =
          '${CurrencySymbols.symbolFor(q.senderCurrency)} ${CurrencySymbols.formatMinor(q.feeMinor, q.senderCurrency)}';
    }
  }

  String _formatIso(String iso) {
    try {
      final dt = DateTime.parse(iso).toLocal();
      final day = dt.day.toString().padLeft(2, '0');
      final month = dt.month.toString().padLeft(2, '0');
      final year = dt.year.toString();
      final hour = dt.hour.toString().padLeft(2, '0');
      final min = dt.minute.toString().padLeft(2, '0');
      return '$day-$month-$year/$hour:$min';
    } catch (_) {
      return iso;
    }
  }

  void copyTransactionId() {
    if (transactionId.value == '—') return;
    Clipboard.setData(ClipboardData(text: transactionId.value));
    SnackBarHelper.showSuccess(
      message: 'Transaction ID copied to clipboard',
      title: 'Copied',
      position: SnackPosition.TOP,
      duration: const Duration(seconds: 2),
    );
  }

  void backToHome() {
    Get.offAllNamed(AppRoutes.home);
  }
}
