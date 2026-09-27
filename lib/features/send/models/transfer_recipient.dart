class TransferRecipient {
  final String uid;
  final String tag;
  final String displayName;
  final String country;
  final String currency;

  const TransferRecipient({
    required this.uid,
    required this.tag,
    required this.displayName,
    required this.country,
    required this.currency,
  });

  factory TransferRecipient.fromJson(Map<String, dynamic> json) {
    return TransferRecipient(
      uid: json['uid']?.toString() ?? '',
      tag: json['tag']?.toString() ?? '',
      displayName: json['display_name']?.toString() ?? '',
      country: json['country']?.toString() ?? '',
      currency: json['currency']?.toString() ?? '',
    );
  }
}
