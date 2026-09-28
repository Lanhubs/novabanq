import 'package:get/get.dart';
import 'package:novabanq/core/network/api_client.dart';
import 'package:novabanq/core/utils/helpers.dart';

class TransferErrorHandler {
  static void handleQuoteError(ApiFailure e) {
    switch (e.code) {
      case 'RECIPIENT_NOT_FOUND':
        showSnack('Recipient not found', 'No one found with that @tag.');
        break;
      case 'SELF_TRANSFER':
        showSnack('Invalid recipient', 'You cannot send money to yourself.');
        break;
      case 'INSUFFICIENT_BALANCE':
        showSnack(
          'Insufficient balance',
          'Your balance cannot cover this transfer.',
        );
        break;
      case 'AMOUNT_INVALID':
        showSnack('Invalid amount', 'Minimum transfer is 1.00.');
        break;
      case 'CORRIDOR_UNSUPPORTED':
        showSnack(
          'Unsupported',
          'Transfers to this currency are not supported yet.',
        );
        break;
      case 'RATE_UNAVAILABLE':
      case 'FX_PROVIDER_UNAVAILABLE':
        showSnack(
          'Rate unavailable',
          'FX rate is unavailable. Try again in a moment.',
        );
        break;
      default:
        showSnack('Error', e.message);
    }
  }

  static void handleExecuteError(ApiFailure e) {
    switch (e.code) {
      case 'PIN_INVALID':
        showSnack('Incorrect PIN', 'Incorrect PIN. Please try again.');
        break;
      case 'PIN_LOCKED':
        showSnack(
          'PIN Locked',
          'Too many wrong attempts. Try again in 20 minutes.',
        );
        break;
      case 'INSUFFICIENT_BALANCE':
        showSnack(
          'Insufficient balance',
          'Your balance cannot cover this transfer.',
        );
        break;
      case 'DUPLICATE_TRANSFER':
        showSnack(
          'Transfer already submitted',
          'This request settled. Open transaction history for its receipt before sending again.',
        );
        break;
      case 'RECIPIENT_NOT_FOUND':
      case 'USER_NOT_FOUND':
        showSnack(
          'Recipient unavailable',
          'Check the recipient tag and try again.',
        );
        break;
      case 'SELF_TRANSFER':
        showSnack('Invalid recipient', 'You cannot send money to yourself.');
        break;
      case 'CORRIDOR_UNSUPPORTED':
        showSnack(
          'Unsupported',
          'Transfers to this currency are not supported yet.',
        );
        break;
      default:
        showSnack('Transfer error', e.message);
    }
  }

  static void showSnack(String title, String message) {
    SnackBarHelper.showError(
      message: message,
      title: title,
      position: SnackPosition.TOP,
      duration: const Duration(seconds: 3),
    );
  }
}
