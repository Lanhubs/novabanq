import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:google_fonts/google_fonts.dart';

class CardDetailsTopBar extends StatelessWidget {
  final String title;

  const CardDetailsTopBar({
    super.key,
    this.title = 'Card details',
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        // Circular Back Button
        InkWell(
          onTap: () => Get.back(),
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
        ),

        // Screen Title (Centered)
        Expanded(
          child: Center(
            child: Text(
              title,
              style: GoogleFonts.outfit(
                fontSize: 17,
                fontWeight: FontWeight.w600,
                color: const Color(0xFF101828),
              ),
            ),
          ),
        ),

        // Right spacer to keep title centered
        const SizedBox(width: 42),
      ],
    );
  }
}
