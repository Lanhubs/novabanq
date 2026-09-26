import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class TagInputField extends StatelessWidget {
  final TextEditingController controller;
  final bool hasError;
  final ValueChanged<String> onChanged;

  const TagInputField({
    super.key,
    required this.controller,
    required this.hasError,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 54,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        color: const Color(0xFFF2F4F7),
        borderRadius: BorderRadius.circular(16),
        border: hasError
            ? Border.all(color: const Color(0xFFFDA29B), width: 1)
            : null,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          const Icon(
            Icons.alternate_email_rounded,
            size: 20,
            color: Color(0xFF101828),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: TextField(
              controller: controller,
              onChanged: onChanged,
              style: GoogleFonts.outfit(
                fontSize: 15,
                fontWeight: FontWeight.w500,
                color: const Color(0xFF101828),
              ),
              decoration: const InputDecoration(
                border: InputBorder.none,
                isDense: true,
                contentPadding: EdgeInsets.zero,
                hintText: 'yourname.ng',
              ),
            ),
          ),
          if (hasError)
            const Icon(
              Icons.do_not_disturb_alt_rounded,
              size: 20,
              color: Color(0xFFF04438),
            )
          else
            const Icon(
              Icons.check_circle_rounded,
              size: 20,
              color: Color(0xFF005100),
            ),
        ],
      ),
    );
  }
}
