import 'package:flutter/material.dart';
import 'package:hugeicons/hugeicons.dart';
import 'card_action_button.dart';

class CardActionsRow extends StatelessWidget {
  final VoidCallback onDetailsTap;
  final VoidCallback onFreezeTap;
  final VoidCallback onLimitTap;
  final VoidCallback onAddCardTap;
  final bool isFrozen;

  const CardActionsRow({
    super.key,
    required this.onDetailsTap,
    required this.onFreezeTap,
    required this.onLimitTap,
    required this.onAddCardTap,
    this.isFrozen = false,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        CardActionButton(
          icon: HugeIcons.strokeRoundedView,
          label: 'Details',
          onTap: onDetailsTap,
        ),
        CardActionButton(
          icon: HugeIcons.strokeRoundedSnow,
          label: isFrozen ? 'Unfreeze' : 'Freeze',
          onTap: onFreezeTap,
        ),
        CardActionButton(
          icon: HugeIcons.strokeRoundedSlidersHorizontal,
          label: 'Limit',
          onTap: onLimitTap,
        ),
        CardActionButton(
          icon: HugeIcons.strokeRoundedAdd01,
          label: 'Add card',
          onTap: onAddCardTap,
        ),
      ],
    );
  }
}
