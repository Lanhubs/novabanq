import "package:flutter/material.dart";

class BackBtn extends StatelessWidget {
  final VoidCallback? onPressed;

  const BackBtn({super.key, this.onPressed});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onPressed,
      borderRadius: BorderRadius.circular(22),
      child: Container(
        width: 42,
        height: 42,
        decoration: const BoxDecoration(
          color: Color(0xFFF2F4F7),
          shape: BoxShape.circle,
        ),
        child: const Center(
          child: Icon(
            Icons.arrow_back_rounded,
            size: 20,
            color: Color(0xFF101828),
          ),
        ),
      ),
    );
  }
}
