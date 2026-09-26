import 'package:flutter/material.dart';
import 'preset_amount_chip.dart';

class PresetAmountChipsRow extends StatelessWidget {
  final ValueChanged<int> onSelectPreset;

  const PresetAmountChipsRow({
    super.key,
    required this.onSelectPreset,
  });

  @override
  Widget build(BuildContext context) {
    const presets = [
      (label: '₦ 500', value: 500),
      (label: '₦ 1,000', value: 1000),
      (label: '₦ 1,500', value: 1500),
      (label: '₦ 2,000', value: 2000),
    ];

    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: presets.map((preset) {
        return PresetAmountChip(
          label: preset.label,
          onTap: () => onSelectPreset(preset.value),
        );
      }).toList(),
    );
  }
}
