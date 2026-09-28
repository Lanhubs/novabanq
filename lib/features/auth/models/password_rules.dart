class PasswordRules {
  const PasswordRules._();

  static bool hasValidLength(String value) =>
      value.length >= 8 && value.length <= 10;

  static bool hasLetter(String value) =>
      value.codeUnits.any((c) =>
          (c >= 65 && c <= 90) || (c >= 97 && c <= 122));

  static bool hasNumber(String value) =>
      value.codeUnits.any((c) => c >= 48 && c <= 57);

  static bool isValid(String value) =>
      hasValidLength(value) && hasLetter(value) && hasNumber(value);
}
