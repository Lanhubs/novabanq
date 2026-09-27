import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class SecurityBiometricTile extends StatelessWidget {
  final bool isEnabled;
  final ValueChanged<bool> onChanged;

  const SecurityBiometricTile({
    super.key,
    required this.isEnabled,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 16),
      decoration: const BoxDecoration(
        border: Border(
          bottom: BorderSide(color: Color(0xFFF2F4F7), width: 1),
        ),
      ),
      child: Row(
        children: [
          // Icon
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: const Color(0xFFF2F4F7),
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Center(
              child: Icon(
                Icons.fingerprint_rounded,
                size: 22,
                color: Color(0xFF344054),
              ),
            ),
          ),
          const SizedBox(width: 14),

          // Text
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Biometric login',
                  style: GoogleFonts.outfit(
                    fontSize: 15,
                    fontWeight: FontWeight.w500,
                    color: const Color(0xFF101828),
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  'Face ID or touch ID for fast login',
                  style: GoogleFonts.outfit(
                    fontSize: 13,
                    color: const Color(0xFF667085),
                  ),
                ),
              ],
            ),
          ),

          // Switch
          Switch(
            value: isEnabled,
            onChanged: onChanged,
            activeThumbColor: Colors.white,
            activeTrackColor: const Color(0xFF12B76A),
            inactiveThumbColor: Colors.white,
            inactiveTrackColor: const Color(0xFFD0D5DD),
            materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
          ),
        ],
      ),
    );
  }
}
