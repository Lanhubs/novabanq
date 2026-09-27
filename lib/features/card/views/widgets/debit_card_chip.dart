import 'package:flutter/material.dart';

class DebitCardChip extends StatelessWidget {
  const DebitCardChip({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 32,
      height: 24,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(5),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Color(0xFFFFDF7D),
            Color(0xFFE0A020),
            Color(0xFFFFE89E),
          ],
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.15),
            blurRadius: 2,
            offset: const Offset(0, 1),
          ),
        ],
      ),
      child: Center(
        child: Container(
          width: 26,
          height: 18,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(3),
            border: Border.all(
              color: const Color(0xFFB57805).withValues(alpha: 0.5),
              width: 0.7,
            ),
          ),
          child: Row(
            children: [
              Expanded(
                child: Container(
                  decoration: BoxDecoration(
                    border: Border(
                      right: BorderSide(
                        color: const Color(0xFFB57805).withValues(alpha: 0.5),
                        width: 0.7,
                      ),
                    ),
                  ),
                ),
              ),
              Expanded(
                child: Container(),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
