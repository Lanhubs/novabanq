import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class CardBlackPromoBanner extends StatelessWidget {
  final VoidCallback onTap;

  const CardBlackPromoBanner({
    super.key,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Stack(
        clipBehavior: Clip.none,
        alignment: Alignment.topCenter,
        children: [
          // Stacked back card peeking from the top (soft pink/purple)
          Positioned(
            top: -15,
            left: 6,
            right: 6,
            child: Container(
              height: 60,
              decoration: BoxDecoration(
                color: const Color(0x8A7CC4F8),
                borderRadius: BorderRadius.circular(16),
              ),
            ),
          ),
          Positioned(
            top: -10,
            left: 6,
            right: 6,
            child: Container(
              height: 60,
              decoration: BoxDecoration(
                color: const Color(0xFFF87CB2),
                borderRadius: BorderRadius.circular(16),
              ),
            ),
          ),

          // Front layer card (#7CC4F8)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 18),
            decoration: BoxDecoration(
              color: const Color(0xFF7CC4F8),
              borderRadius: BorderRadius.circular(16),
              boxShadow: [
                BoxShadow(
                  color: const Color(0xFF7CC4F8).withValues(alpha: 0.28),
                  blurRadius: 16,
                  offset: const Offset(0, 6),
                ),
              ],
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                // Text Column
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        'Get a virtual black card',
                        style: GoogleFonts.outfit(
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                          color: Colors.white,
                          letterSpacing: -0.2,
                        ),
                      ),
                      const SizedBox(height: 5),
                      Text(
                        'Pay online with your black card easily\nfrom anywhere in Africa.',
                        style: GoogleFonts.outfit(
                          fontSize: 11.5,
                          fontWeight: FontWeight.w400,
                          color: Colors.white.withValues(alpha: 0.95),
                          height: 1.35,
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(width: 8),

                // 3D Metallic Coins Graphic
                Image.asset(
                  'assets/icons/currencies.png',
                  width: 90,
                  height: 76,
                  fit: BoxFit.contain,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
