part of 'home_controller.dart';

extension HomeTransactionsFlow on HomeController {
  Future<void> loadTransactions({int limit = 20, bool refresh = false}) async {
    while (_transactionRequest != null) {
      await _transactionRequest;
    }
    if (!refresh && _loadedTransactionLimit >= limit) return;
    if (!FirebaseBootstrap.ready) {
      transactionsError.value = 'Sign in to view transactions.';
      return;
    }
    final request = _fetchTransactions(limit);
    _transactionRequest = request;
    try {
      await request;
    } finally {
      _transactionRequest = null;
    }
  }

  Future<void> _fetchTransactions(int limit) async {
    isTransactionsLoading.value = true;
    transactionsError.value = '';
    try {
      final page = await TransactionsApi(
        ApiClient(),
      ).getTransactions(limit: limit);
      transactions.assignAll(page.items);
      _loadedTransactionLimit = limit;
      transactionsError.value = '';
    } on ApiFailure catch (failure) {
      transactionsError.value = switch (failure.code) {
        'AUTH_REQUIRED' || 'AUTH_INVALID' => 'Sign in to view transactions.',
        'NETWORK_ERROR' => 'Check your connection and try again.',
        _ => failure.message,
      };
    } catch (_) {
      transactionsError.value = 'Unable to load transactions. Try again.';
    } finally {
      isTransactionsLoading.value = false;
    }
  }

  Future<void> refreshTransactions() => loadTransactions(
    limit: _loadedTransactionLimit > 0 ? _loadedTransactionLimit : 20,
    refresh: true,
  );
}
