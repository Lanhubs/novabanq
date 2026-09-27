class VirtualAccountInfo {
  final String accountNumber;
  final String bankName;
  final String accountName;
  final String currency;
  final String country;

  const VirtualAccountInfo({
    required this.accountNumber,
    required this.bankName,
    required this.accountName,
    required this.currency,
    required this.country,
  });

  factory VirtualAccountInfo.fromJson(Map<String, dynamic> json) {
    return VirtualAccountInfo(
      accountNumber: json['account_number']?.toString() ?? '',
      bankName: json['bank_name']?.toString() ?? 'Novabanq MFB',
      accountName: json['account_name']?.toString() ?? '',
      currency: json['currency']?.toString() ?? 'NGN',
      country: json['country']?.toString() ?? 'NG',
    );
  }
}
