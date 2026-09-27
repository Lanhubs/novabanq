import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:novabanq/core/network/api_client.dart';
import 'package:novabanq/core/network/transfer_api.dart';
import 'package:novabanq/core/utils/currency_symbols.dart';
import 'package:novabanq/core/utils/idempotency.dart';
import 'package:novabanq/core/utils/transfer_attempt_store.dart';
import 'package:novabanq/features/send/bindings/transfer_success_binding.dart';
import 'package:novabanq/features/send/models/transfer_quote.dart';
import 'package:novabanq/features/send/models/transfer_result.dart';
import 'package:novabanq/features/send/views/transfer_success_screen.dart';
import 'package:novabanq/features/home/models/home_country_currency.dart';
import 'package:novabanq/features/home/controllers/home_controller.dart';
import '../views/widgets/confirm_transaction_bottom_sheet.dart';
import '../views/widgets/transaction_pin_bottom_sheet.dart';
import 'transfer_error_handler.dart';

part 'send_amount_execution.dart';
part 'send_amount_sheets.dart';

class SendAmountController extends GetxController {
  final recipientName = 'Recipient'.obs;
  final recipientAccount = '—'.obs;
  final recipientTag = ''.obs;
  final senderCurrency = ''.obs;
  final amount = '0'.obs;
  final sourceAccountTitle = 'Account'.obs;
  final sourceAccountBalance = '—'.obs;
  final transactionPin = ''.obs;
  final isKeypadVisible = false.obs;
  final isLoading = false.obs;
  final isExecuting = false.obs;
  final isAccountReady = false.obs;
  final quote = Rxn<TransferQuote>();
  String? _idempotencyKey;
  String? _attemptFingerprint;
  TransferApi get api => _api ??= TransferApi(ApiClient());
  TransferApi? _api;
  HomeCountryCurrency? _fromCountry;
  HomeCountryCurrency? _toCountry;

  @override
  void onInit() {
    super.onInit();
    final args = Get.arguments;
    if (args is Map && args['recipient_tag'] != null) {
      recipientTag.value = args['recipient_tag'].toString();
      recipientAccount.value = '@${recipientTag.value}';
    }
    if (args is Map) {
      _fromCountry = args['from_country'] is HomeCountryCurrency
          ? args['from_country'] as HomeCountryCurrency
          : null;
      _toCountry = args['to_country'] is HomeCountryCurrency
          ? args['to_country'] as HomeCountryCurrency
          : null;
    }
    ever(amount, (_) => quote.value = null);
    _loadAccount();
  }

  Future<void> _loadAccount() async {
    try {
      final account = await api.getAccount();
      senderCurrency.value = account.currency;
      sourceAccountTitle.value = '${account.currency} Account';
      sourceAccountBalance.value = account.balanceDisplay;
      isAccountReady.value = true;
    } on ApiFailure catch (e) {
      TransferErrorHandler.showSnack('Account unavailable', e.message);
    } catch (_) {
      TransferErrorHandler.showSnack(
        'Account unavailable',
        'Check your connection and try again.',
      );
    }
  }

  String get beneficiaryReceivesText {
    final q = quote.value;
    if (q == null || q.isExpired) {
      return 'Get a quote to see what the beneficiary receives';
    }
    final symbol = CurrencySymbols.symbolFor(q.recipient.currency);
    return 'Beneficiary receives $symbol ${CurrencySymbols.formatMinor(q.receiveAmountMinor, q.recipient.currency)}';
  }

  void appendDigit(String digit) {
    if (amount.value == '0') {
      amount.value = digit;
    } else if (amount.value.length < 9) {
      amount.value += digit;
    }
  }

  void deleteDigit() => amount.value = amount.value.length > 1
      ? amount.value.substring(0, amount.value.length - 1)
      : '0';
  void clearAmount() => amount.value = '0';
  void setPresetAmount(int preset) => amount.value = preset.toString();
  void openKeypad() => isKeypadVisible.value = true;
  void hideKeypad() => isKeypadVisible.value = false;
  void toggleKeypad() => isKeypadVisible.value = !isKeypadVisible.value;

  Future<void> onContinue() async {
    if (isLoading.value) return;
    hideKeypad();
    if (!isAccountReady.value) {
      await _loadAccount();
      if (!isAccountReady.value) return;
    }
    if (_fromCountry != null &&
        _fromCountry!.currencyCode != senderCurrency.value) {
      TransferErrorHandler.showSnack(
        'Corridor mismatch',
        'Your account uses ${senderCurrency.value}. Select that country as From.',
      );
      return;
    }
    final minor = CurrencySymbols.parseMinor(
      amount.value,
      senderCurrency.value,
    );
    if (minor == null || minor < 100) {
      TransferErrorHandler.showSnack(
        'Invalid amount',
        senderCurrency.value == 'XOF'
            ? 'Minimum transfer is 100 CFA.'
            : 'Minimum transfer is 1.00.',
      );
      return;
    }
    try {
      isLoading.value = true;
      final q = await api.getQuote(
        recipientTag: recipientTag.value,
        amountMinor: minor,
      );
      if (q.isExpired ||
          q.recipient.tag.isEmpty ||
          q.recipient.currency.isEmpty ||
          q.sendAmountMinor != minor ||
          q.receiveAmountMinor <= 0 ||
          q.totalDebitMinor < q.sendAmountMinor ||
          q.senderCurrency != senderCurrency.value) {
        throw const ApiFailure(
          'INVALID_QUOTE',
          'Unable to verify this quote. Please try again.',
        );
      }
      if (_toCountry != null &&
          q.recipient.country.toUpperCase() != _toCountry!.countryCode) {
        throw const ApiFailure(
          'CORRIDOR_MISMATCH',
          'The recipient belongs to another country. Update the To country.',
        );
      }
      quote.value = q;
      recipientName.value = q.recipient.displayName.isEmpty
          ? '@${q.recipient.tag}'
          : q.recipient.displayName;
      showConfirmTransactionSheet(q);
    } on ApiFailure catch (e) {
      TransferErrorHandler.handleQuoteError(e);
    } catch (_) {
      TransferErrorHandler.showSnack(
        'Error',
        'Unable to get quote. Try again.',
      );
    } finally {
      isLoading.value = false;
    }
  }
}
