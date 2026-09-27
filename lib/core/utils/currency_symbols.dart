class CurrencySymbols {
  static String symbolFor(String currency) {
    switch (currency.toUpperCase()) {
      case 'NGN':
        return '₦';
      case 'GHS':
        return '₵';
      case 'KES':
        return 'KSh';
      case 'ZAR':
        return 'R';
      case 'XOF':
        return 'CFA';
      default:
        return currency;
    }
  }

  static int multiplierFor(String currency) {
    if (currency.toUpperCase() == 'XOF') {
      return 1;
    }
    return 100;
  }

  static int toMinor(num amount, String currency) {
    return (amount * multiplierFor(currency)).round();
  }

  static int? parseMinor(String amount, String currency) {
    final clean = amount.replaceAll(',', '').trim();
    final decimals = multiplierFor(currency) == 1 ? 0 : 2;
    final parts = clean.split('.');
    if (parts.isEmpty ||
        parts.length > 2 ||
        parts.first.isEmpty ||
        parts.any(
          (part) =>
              part.isEmpty ||
              part.codeUnits.any((unit) => unit < 48 || unit > 57),
        ) ||
        (parts.length == 2 &&
            (decimals == 0 || parts.last.length > decimals))) {
      return null;
    }
    final major = int.tryParse(parts.first);
    if (major == null) return null;
    final fraction = parts.length == 2
        ? int.parse(parts.last.padRight(2, '0'))
        : 0;
    return major * multiplierFor(currency) + fraction;
  }

  static String formatMinor(int minorAmount, String currency) {
    final mult = multiplierFor(currency);
    if (mult == 1) {
      return _addCommas(minorAmount.toString());
    }
    final major = minorAmount ~/ 100;
    final cents = (minorAmount % 100).abs().toString().padLeft(2, '0');
    return '${_addCommas(major.toString())}.$cents';
  }

  static String _addCommas(String text) {
    final isNegative = text.startsWith('-');
    final digits = isNegative ? text.substring(1) : text;
    final chars = digits.split('').reversed.toList();
    final chunks = <String>[];
    for (int i = 0; i < chars.length; i++) {
      if (i > 0 && i % 3 == 0) {
        chunks.add(',');
      }
      chunks.add(chars[i]);
    }
    final result = chunks.reversed.join();
    return isNegative ? '-$result' : result;
  }
}
