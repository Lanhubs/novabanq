import 'package:flutter/services.dart';
import 'package:get/get.dart';
import 'package:novabanq/core/network/api_client.dart';
import 'package:novabanq/core/network/transactions_api.dart';
import 'package:novabanq/core/utils/helpers.dart';
import 'package:novabanq/features/send/models/transaction_summary.dart';

class TransactionDetailController extends GetxController {
  final String transactionId;

  TransactionDetailController({required this.transactionId});

  final transaction = Rx<TransactionSummary?>(null);
  final isLoading = true.obs;
  final error = ''.obs;

  @override
  void onInit() {
    super.onInit();
    loadTransactionDetails();
  }

  Future<void> loadTransactionDetails() async {
    isLoading.value = true;
    error.value = '';

    try {
      final transactionsApi = TransactionsApi(ApiClient());
      final details = await transactionsApi.getTransaction(transactionId);
      transaction.value = details;
      error.value = '';
    } on ApiFailure catch (failure) {
      error.value = _getErrorMessage(failure);
      _showErrorFeedback(failure);
    } catch (e) {
      error.value = 'Failed to load transaction details';
      SnackBarHelper.showError(
        message: 'Unable to load transaction details. Please try again.',
        title: 'Error',
      );
    } finally {
      isLoading.value = false;
    }
  }

  String _getErrorMessage(ApiFailure failure) {
    switch (failure.status) {
      case 404:
        return 'Transaction not found';
      case 401:
        return 'Authentication required';
      case 403:
        return 'Access denied';
      default:
        return failure.message.isNotEmpty
            ? failure.message
            : 'Failed to load transaction';
    }
  }

  void _showErrorFeedback(ApiFailure failure) {
    if (failure.status == 404) {
      SnackBarHelper.showWarning(
        message: 'This transaction could not be found.',
        title: 'Not Found',
      );
    } else if (failure.status == 401 || failure.status == 403) {
      SnackBarHelper.showError(
        message: 'You don\'t have access to this transaction.',
        title: 'Access Denied',
      );
    } else {
      SnackBarHelper.showNetworkError(
        message: 'Failed to load transaction details',
        onRetry: loadTransactionDetails,
      );
    }
  }

  void onRetry() {
    loadTransactionDetails();
  }

  void goBack() => Get.back();

  void copyTransactionId() {
    if (transaction.value != null) {
      Clipboard.setData(ClipboardData(text: transaction.value!.transactionId));
      SnackBarHelper.showSuccess(
        message: 'Transaction ID copied to clipboard',
        title: 'Copied',
      );
    }
  }
}
