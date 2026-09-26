import 'package:flutter/material.dart';

class CountryItem {
  final String name;
  final String code;
  final String dialCode;
  final Widget flagWidget;

  const CountryItem({
    required this.name,
    required this.code,
    required this.dialCode,
    required this.flagWidget,
  });

  String get displayText => "$name $dialCode";
}

/// Helper widget to draw crisp country flags matching the design
class CountryFlagBadge extends StatelessWidget {
  final String code;
  final double width;
  final double height;

  const CountryFlagBadge({
    super.key,
    required this.code,
    this.width = 24,
    this.height = 16,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(2.5),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.08),
            blurRadius: 1,
            offset: const Offset(0, 0.5),
          ),
        ],
      ),
      clipBehavior: Clip.antiAlias,
      child: _CountryFlagContent(code: code),
    );
  }
}

class _CountryFlagContent extends StatelessWidget {
  final String code;

  const _CountryFlagContent({required this.code});

  @override
  Widget build(BuildContext context) {
    switch (code) {
      case 'NG': // Nigeria: Green - White - Green vertical stripes
        return Row(
          children: [
            Expanded(child: Container(color: const Color(0xFF008751))),
            Expanded(child: Container(color: Colors.white)),
            Expanded(child: Container(color: const Color(0xFF008751))),
          ],
        );
      case 'GH': // Ghana: Red - Yellow (with star) - Green horizontal
        return Stack(
          alignment: Alignment.center,
          children: [
            Column(
              children: [
                Expanded(child: Container(color: const Color(0xFFCE1126))),
                Expanded(child: Container(color: const Color(0xFFFCD116))),
                Expanded(child: Container(color: const Color(0xFF006B3F))),
              ],
            ),
            const Icon(Icons.star, size: 7, color: Colors.black),
          ],
        );
      case 'SN': // Senegal: Green - Yellow (with star) - Red vertical
        return Stack(
          alignment: Alignment.center,
          children: [
            Row(
              children: [
                Expanded(child: Container(color: const Color(0xFF00853F))),
                Expanded(child: Container(color: const Color(0xFFFDEF42))),
                Expanded(child: Container(color: const Color(0xFFE31B23))),
              ],
            ),
            const Icon(Icons.star, size: 7, color: Color(0xFF00853F)),
          ],
        );
      case 'CI': // Ivory Coast: Orange - White - Green vertical
        return Row(
          children: [
            Expanded(child: Container(color: const Color(0xFFF77F00))),
            Expanded(child: Container(color: Colors.white)),
            Expanded(child: Container(color: const Color(0xFF009E60))),
          ],
        );
      case 'CM': // Cameroon: Green - Red (with yellow star) - Yellow vertical
        return Stack(
          alignment: Alignment.center,
          children: [
            Row(
              children: [
                Expanded(child: Container(color: const Color(0xFF007A5E))),
                Expanded(child: Container(color: const Color(0xFFCE1126))),
                Expanded(child: Container(color: const Color(0xFFFCD116))),
              ],
            ),
            const Icon(Icons.star, size: 7, color: Color(0xFFFCD116)),
          ],
        );
      case 'KE': // Kenya: Black, Red, Green horizontal
        return Column(
          children: [
            Expanded(child: Container(color: Colors.black)),
            Container(height: 1, color: Colors.white),
            Expanded(child: Container(color: const Color(0xFF990000))),
            Container(height: 1, color: Colors.white),
            Expanded(child: Container(color: const Color(0xFF006600))),
          ],
        );
      case 'ZA':
        return Row(
          children: [
            Expanded(child: Container(color: const Color(0xFF007A4D))),
            Expanded(child: Container(color: const Color(0xFFFFB612))),
            Expanded(child: Container(color: const Color(0xFFDE3831))),
          ],
        );
      default:
        return Container(color: Colors.grey.shade300);
    }
  }
}
