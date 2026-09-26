import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class KeypadKeyData {
  final String number;
  final String letters;

  const KeypadKeyData(this.number, this.letters);
}

class KeypadKeyButton extends StatelessWidget {
  final KeypadKeyData data;
  final ValueChanged<String> onKeyPress;

  const KeypadKeyButton({
    super.key,
    required this.data,
    required this.onKeyPress,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(8),
      elevation: 0.5,
      shadowColor: Colors.black.withValues(alpha: 0.08),
      child: InkWell(
        onTap: () => onKeyPress(data.number),
        borderRadius: BorderRadius.circular(8),
        child: Container(
          height: 52,
          alignment: Alignment.center,
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                data.number,
                style: GoogleFonts.outfit(
                  fontSize: 22,
                  fontWeight: FontWeight.w600,
                  color: const Color(0xFF101828),
                  height: 1.1,
                ),
              ),
              if (data.letters.isNotEmpty)
                Text(
                  data.letters,
                  style: GoogleFonts.outfit(
                    fontSize: 9,
                    fontWeight: FontWeight.w600,
                    letterSpacing: 1.2,
                    color: const Color(0xFF101828),
                    height: 1.0,
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
