import 'package:flutter/material.dart';

class CardControlSwitch extends StatelessWidget {
  final bool value;
  final ValueChanged<bool> onChanged;

  const CardControlSwitch({
    super.key,
    required this.value,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => onChanged(!value),
      behavior: HitTestBehavior.opaque,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        width: 48,
        height: 28,
        padding: const EdgeInsets.symmetric(horizontal: 3),
        decoration: BoxDecoration(
          color: value ? const Color(0xFF034E1B) : const Color(0xFFE2E0EC),
          borderRadius: BorderRadius.circular(20),
          border: value
              ? null
              : Border.all(
                  color: const Color(0xFF6B6580),
                  width: 1.5,
                ),
        ),
        child: AnimatedAlign(
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeInOut,
          alignment: value ? Alignment.centerRight : Alignment.centerLeft,
          child: Container(
            width: value ? 22 : 16,
            height: value ? 22 : 16,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: value ? Colors.white : const Color(0xFF7A758D),
              boxShadow: value
                  ? [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.15),
                        blurRadius: 2,
                        offset: const Offset(0, 1),
                      ),
                    ]
                  : null,
            ),
          ),
        ),
      ),
    );
  }
}
