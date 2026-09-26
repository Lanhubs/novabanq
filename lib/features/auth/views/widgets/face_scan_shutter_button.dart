import 'package:flutter/material.dart';

class FaceScanShutterButton extends StatelessWidget {
  final VoidCallback onTap;

  const FaceScanShutterButton({
    super.key,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 72,
        height: 72,
        decoration: BoxDecoration(
          color: const Color(0xFF005100),
          shape: BoxShape.circle,

        ),
        child: Center(
          child: Container(
            width: 58,
            height: 58,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(
                color: Colors.white.withValues(alpha: 0.3),
                width: 2,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
