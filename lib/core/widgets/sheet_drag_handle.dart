import 'package:flutter/material.dart';

class SheetDragHandle extends StatelessWidget {
  const SheetDragHandle({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 48,
      height: 5,
      decoration: BoxDecoration(
        color: const Color(0xFFD0D5DD),
        borderRadius: BorderRadius.circular(3),
      ),
    );
  }
}
