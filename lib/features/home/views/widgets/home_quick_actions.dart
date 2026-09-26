import 'package:flutter/material.dart';
import 'package:hugeicons/hugeicons.dart';
import 'quick_action_button.dart';

class HomeQuickActions extends StatelessWidget {
  final Function(String action) onActionTap;

  const HomeQuickActions({
    super.key,
    required this.onActionTap,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        // 1. Send Action
        QuickActionButton(
          icon: HugeIcons.strokeRoundedSent,
          label: 'Send',
          onTap: () => onActionTap('Send'),
        ),

        const SizedBox(width: 40),

        // 2. Receive Action
        QuickActionButton(
          icon: HugeIcons.strokeRoundedArrowDownLeft01,
          label: 'Receive',
          onTap: () => onActionTap('Receive'),
        ),

        const SizedBox(width: 40),

        // 3. Convert Action
        QuickActionButton(
          icon: HugeIcons.strokeRoundedExchange01,
          label: 'Convert',
          onTap: () => onActionTap('Convert'),
        ),
      ],
    );
  }
}
