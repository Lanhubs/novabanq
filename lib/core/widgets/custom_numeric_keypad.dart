import 'package:flutter/material.dart';
import 'keypad_key_button.dart';

class CustomNumericKeypad extends StatelessWidget {
  final ValueChanged<String> onKeyPress;
  final VoidCallback onBackspace;
  final VoidCallback? onClear;

  const CustomNumericKeypad({
    super.key,
    required this.onKeyPress,
    required this.onBackspace,
    this.onClear,
  });

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Container(
        decoration: BoxDecoration(
          color: const Color(0xFFF2F4F7),
          borderRadius: const BorderRadius.only(
            topLeft: Radius.circular(24),
            topRight: Radius.circular(24),
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.06),
              blurRadius: 10,
              offset: const Offset(0, -2),
            ),
          ],
        ),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Row 1: 1, 2 (ABC), 3 (DEF)
              _KeypadRow(
                keys: const [
                  KeypadKeyData('1', ''),
                  KeypadKeyData('2', 'A B C'),
                  KeypadKeyData('3', 'D E F'),
                ],
                onKeyPress: onKeyPress,
              ),
              const SizedBox(height: 8),

              // Row 2: 4 (GHI), 5 (JKL), 6 (MNO)
              _KeypadRow(
                keys: const [
                  KeypadKeyData('4', 'G H I'),
                  KeypadKeyData('5', 'J K L'),
                  KeypadKeyData('6', 'M N O'),
                ],
                onKeyPress: onKeyPress,
              ),
              const SizedBox(height: 8),

              // Row 3: 7 (PQRS), 8 (TUV), 9 (WXYZ)
              _KeypadRow(
                keys: const [
                  KeypadKeyData('7', 'P Q R S'),
                  KeypadKeyData('8', 'T U V'),
                  KeypadKeyData('9', 'W X Y Z'),
                ],
                onKeyPress: onKeyPress,
              ),
              const SizedBox(height: 8),

              // Row 4: Empty, 0, Backspace
              Row(
                children: [
                  const Expanded(child: SizedBox(height: 52)),
                  const SizedBox(width: 8),
                  Expanded(
                    child: KeypadKeyButton(
                      data: const KeypadKeyData('0', ''),
                      onKeyPress: onKeyPress,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: InkWell(
                      onTap: onBackspace,
                      onLongPress: onClear,
                      borderRadius: BorderRadius.circular(8),
                      child: Container(
                        height: 52,
                        alignment: Alignment.center,
                        child: const Icon(
                          Icons.backspace_outlined,
                          size: 24,
                          color: Color(0xFF101828),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _KeypadRow extends StatelessWidget {
  final List<KeypadKeyData> keys;
  final ValueChanged<String> onKeyPress;

  const _KeypadRow({
    required this.keys,
    required this.onKeyPress,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        for (int i = 0; i < keys.length; i++) ...[
          if (i > 0) const SizedBox(width: 8),
          Expanded(
            child: KeypadKeyButton(
              data: keys[i],
              onKeyPress: onKeyPress,
            ),
          ),
        ],
      ],
    );
  }
}
