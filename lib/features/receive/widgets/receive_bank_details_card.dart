import 'package:flutter/material.dart';
import 'receive_detail_item.dart';

class ReceiveBankDetailsCard extends StatelessWidget {
  final String accountName;
  final String accountNumber;
  final String bankName;
  final VoidCallback onCopyName;
  final VoidCallback onCopyNumber;
  final VoidCallback onCopyBank;

  const ReceiveBankDetailsCard({
    super.key,
    required this.accountName,
    required this.accountNumber,
    required this.bankName,
    required this.onCopyName,
    required this.onCopyNumber,
    required this.onCopyBank,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        color: Color(0x21E7E9EC),
        borderRadius: BorderRadius.circular(16),
       
      ),
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
      child: Column(
        children: [
          ReceiveDetailItem(
            label: 'Account name',
            value: accountName,
            onCopy: onCopyName,
          ),
          const Divider(height: 1, color: Color(0xFFF2F4F7)),
          ReceiveDetailItem(
            label: 'Account number',
            value: accountNumber,
            onCopy: onCopyNumber,
          ),
          const Divider(height: 1, color: Color(0xFFF2F4F7)),
          ReceiveDetailItem(
            label: 'Bank',
            value: bankName,
            onCopy: onCopyBank,
          ),
        ],
      ),
    );
  }
}
