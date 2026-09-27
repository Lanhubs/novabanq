class UserAccountBalance {
  final String currency;
  final int balanceMinor;
  final String balanceDisplay;
  final String updatedAt;

  const UserAccountBalance({
    required this.currency,
    required this.balanceMinor,
    required this.balanceDisplay,
    required this.updatedAt,
  });

  factory UserAccountBalance.fromJson(Map<String, dynamic> json) {
    return UserAccountBalance(
      currency: json['currency']?.toString() ?? 'NGN',
      balanceMinor: (json['balance_minor'] as num?)?.toInt() ?? 0,
      balanceDisplay: json['balance_display']?.toString() ?? '0.00',
      updatedAt: json['updated_at']?.toString() ?? '',
    );
  }
}
