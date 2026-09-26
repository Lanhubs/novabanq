import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Reusable input field styled with the specified #E7E9ECD9 background
class AuthTextField extends StatelessWidget {
  final TextEditingController? controller;
  final String hintText;
  final String? label;
  final TextInputType keyboardType;
  final bool obscureText;
  final Widget? suffixIcon;
  final ValueChanged<String>? onChanged;
  final bool autofocus;

  const AuthTextField({
    super.key,
    this.controller,
    required this.hintText,
    this.label,
    this.keyboardType = TextInputType.text,
    this.obscureText = false,
    this.suffixIcon,
    this.onChanged,
    this.autofocus = false,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (label != null) ...[
          Text(
            label!,
            style: GoogleFonts.outfit(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: const Color(0xFF111111),
            ),
          ),
          const SizedBox(height: 8),
        ],
        Container(
          decoration: BoxDecoration(
            color: const Color(0xD9E7E9EC), // Exact #E7E9ECD9 background requested
            borderRadius: BorderRadius.circular(10),
          ),
          child: TextField(
            controller: controller,
            autofocus: autofocus,
            keyboardType: keyboardType,
            obscureText: obscureText,
            onChanged: onChanged,
            style: GoogleFonts.outfit(
              fontSize: 15,
              fontWeight: FontWeight.w500,
              color: const Color(0xFF101828),
            ),
            cursorColor: const Color(0xFF005100),
            decoration: InputDecoration(
              hintText: hintText,
              hintStyle: GoogleFonts.outfit(
                fontSize: 14,
                fontWeight: FontWeight.w400,
                color: const Color(0xFF667085),
              ),
              suffixIcon: suffixIcon,
              border: InputBorder.none,
              contentPadding: const EdgeInsets.symmetric(
                horizontal: 16,
                vertical: 16,
              ),
            ),
          ),
        ),
      ],
    );
  }
}
