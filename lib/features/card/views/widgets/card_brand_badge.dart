import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class CardBrandBadge extends StatelessWidget {
  final String logoType;

  const CardBrandBadge({
    super.key,
    required this.logoType,
  });

  @override
  Widget build(BuildContext context) {
    if (logoType == 'spotify') {
      return Container(
        width: 44,
        height: 44,
        decoration: const BoxDecoration(
          shape: BoxShape.circle,
          color: Color(0xFFD8F3DC),
        ),
        child: Center(
          child: Container(
            width: 30,
            height: 30,
            decoration: const BoxDecoration(
              shape: BoxShape.circle,
              color: Color(0xFF1DB954),
            ),
            child: const Center(
              child: Icon(
                Icons.graphic_eq_rounded,
                color: Colors.black,
                size: 18,
              ),
            ),
          ),
        ),
      );
    }

    if (logoType == 'jumia') {
      return Container(
        width: 44,
        height: 44,
        decoration: const BoxDecoration(
          shape: BoxShape.circle,
          color: Color(0xFFFFEDD5),
        ),
        child: Center(
          child: Container(
            width: 28,
            height: 28,
            decoration: BoxDecoration(
              color: const Color(0xFFF97316),
              borderRadius: BorderRadius.circular(6),
            ),
            child: const Center(
              child: Icon(
                Icons.star_rate_rounded,
                color: Colors.white,
                size: 18,
              ),
            ),
          ),
        ),
      );
    }

    // Default / Uber
    return Container(
      width: 44,
      height: 44,
      decoration: const BoxDecoration(
        shape: BoxShape.circle,
        color: Color(0xFFE5E7EB),
      ),
      child: Center(
        child: Text(
          'Uber',
          style: GoogleFonts.outfit(
            fontSize: 10,
            fontWeight: FontWeight.w700,
            color: Colors.black,
          ),
        ),
      ),
    );
  }
}
