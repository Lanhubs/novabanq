import 'package:flutter/material.dart';
import 'package:novabanq/core/widgets/custom_numeric_keypad.dart';
import 'package:novabanq/core/widgets/sheet_drag_handle.dart';

class NumericKeypadBottomSheet extends StatelessWidget {
  final ValueChanged<String> onKeyPress;
  final VoidCallback onBackspace;
  final VoidCallback? onClear;

  const NumericKeypadBottomSheet({
    super.key,
    required this.onKeyPress,
    required this.onBackspace,
    this.onClear,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: Color(0xFFF2F4F7),
        borderRadius: BorderRadius.only(
          topLeft: Radius.circular(24),
          topRight: Radius.circular(24),
        ),
      ),
      child: SafeArea(
        top: false,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SheetDragHandle(),
            CustomNumericKeypad(
              onKeyPress: onKeyPress,
              onBackspace: onBackspace,
              onClear: onClear,
            ),
          ],
        ),
      ),
    );
  }
}
