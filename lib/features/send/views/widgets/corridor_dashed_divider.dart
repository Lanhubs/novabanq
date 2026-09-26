import 'package:flutter/material.dart';

class CorridorDashedDivider extends StatelessWidget {
  const CorridorDashedDivider({super.key});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final dashWidth = 5.0;
          final dashSpace = 4.0;
          final dashCount =
              (constraints.maxWidth / (dashWidth + dashSpace)).floor();

          return Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: List.generate(dashCount, (_) {
              return SizedBox(
                width: dashWidth,
                height: 1.2,
                child: const DecoratedBox(
                  decoration: BoxDecoration(
                    color: Color(0xFFD0D5DD),
                  ),
                ),
              );
            }),
          );
        },
      ),
    );
  }
}
