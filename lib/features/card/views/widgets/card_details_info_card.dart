import 'package:flutter/material.dart';
import 'card_controls_tile.dart';
import 'card_info_item.dart';

class CardDetailsInfoCard extends StatelessWidget {
  final String accountName;
  final String cardNumber;
  final String expiryDate;
  final String cvv;
  final VoidCallback onCopyAccountName;
  final VoidCallback onCopyCardNumber;
  final VoidCallback onCopyExpiryDate;
  final VoidCallback onCopyCvv;
  final VoidCallback onControlsTap;

  const CardDetailsInfoCard({
    super.key,
    required this.accountName,
    required this.cardNumber,
    required this.expiryDate,
    required this.cvv,
    required this.onCopyAccountName,
    required this.onCopyCardNumber,
    required this.onCopyExpiryDate,
    required this.onCopyCvv,
    required this.onControlsTap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: const Color(0xFFF9FAFB),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: const Color(0xFFEAECF0),
          width: 1,
        ),
      ),
      child: Column(
        children: [
          CardInfoItem(
            label: 'Account name',
            value: accountName,
            onCopy: onCopyAccountName,
          ),
          const SizedBox(height: 4),
          CardInfoItem(
            label: 'Card number',
            value: cardNumber,
            onCopy: onCopyCardNumber,
          ),
          const SizedBox(height: 4),
          CardInfoItem(
            label: 'Expiry date',
            value: expiryDate,
            onCopy: onCopyExpiryDate,
          ),
          const SizedBox(height: 4),
          CardInfoItem(
            label: 'CVV',
            value: cvv,
            onCopy: onCopyCvv,
          ),
          const SizedBox(height: 4),
          CardControlsTile(
            onTap: onControlsTap,
          ),
        ],
      ),
    );
  }
}
