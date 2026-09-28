import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:novabanq/core/network/nova_api.dart';
import 'package:novabanq/core/utils/currency_symbols.dart';
import 'package:novabanq/features/home/controllers/home_controller.dart';
import 'package:novabanq/features/home/controllers/nova_conversation_controller.dart';
import 'package:novabanq/features/home/models/nova_transfer.dart';
import 'package:novabanq/features/home/views/widgets/nova_pin_sheet.dart';
import 'package:novabanq/features/send/bindings/transfer_success_binding.dart';
import 'package:novabanq/features/send/views/transfer_success_screen.dart';
import 'package:novabanq/features/send/views/widgets/confirm_transaction_bottom_sheet.dart';

class NovaTransferFlow {
  const NovaTransferFlow._();

  static Future<void> confirm(
    BuildContext context,
    NovaTransferPreview preview,
    NovaApi api,
    NovaConversationController conversation,
  ) async {
    final quote = preview.quote;
    final sender = quote.senderCurrency;
    final receiver = quote.recipient.currency;
    String money(int minor, String currency) =>
        '${CurrencySymbols.symbolFor(currency)} ${CurrencySymbols.formatMinor(minor, currency)}';
    final accepted = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) => ConfirmTransactionBottomSheet(
        recipientName:
            '${quote.recipient.displayName} (@${quote.recipient.tag})',
        fromAccount: '$sender account',
        amountFromAccount: money(quote.totalDebitMinor, sender),
        amountToBeneficiary: money(quote.receiveAmountMinor, receiver),
        fee: money(quote.feeMinor, sender),
        scheduleAt: preview.executeAt == null
            ? null
            : _date(preview.executeAt!.toLocal()),
        confirmText: preview.isScheduled ? 'Schedule payment' : 'Send money',
        onConfirm: () => Navigator.of(sheetContext).pop(true),
      ),
    );
    if (accepted != true || !context.mounted) return;
    if (quote.isExpired) {
      conversation.report(
        'The quote expired. Send the instruction again to review a fresh quote.',
        isError: true,
      );
      return;
    }
    final result = await showModalBottomSheet<NovaTransferResult>(
      context: context,
      isScrollControlled: true,
      isDismissible: false,
      enableDrag: false,
      backgroundColor: Colors.transparent,
      builder: (_) => NovaPinSheet(api: api, preview: preview),
    );
    if (result == null || !context.mounted) return;
    switch (result) {
      case NovaImmediateTransfer(:final transfer):
        if (Get.isRegistered<HomeController>()) {
          final home = Get.find<HomeController>();
          home.loadAccount();
          home.refreshTransactions();
        }
        Navigator.of(context).pop();
        Get.to(
          () => const TransferSuccessScreen(),
          binding: TransferSuccessBinding(),
          arguments: transfer,
        );
      case NovaScheduledTransfer(
        :final recipientTag,
        :final executeAt,
        :final amountMinor,
        :final currency,
        :final status,
        :final id,
      ):
        conversation.report(
          '$status: ${money(amountMinor, currency)} to @$recipientTag on '
          '${_date(executeAt.toLocal())}. Reference: $id',
        );
    }
  }

  static String _date(DateTime date) =>
      '${date.day}/${date.month}/${date.year} '
      '${date.hour.toString().padLeft(2, '0')}:'
      '${date.minute.toString().padLeft(2, '0')}';
}
