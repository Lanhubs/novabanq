import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class HomePromoBanner extends StatelessWidget {
  final VoidCallback? onTap;

  const HomePromoBanner({super.key, this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Stack(
        clipBehavior: Clip.none,
        alignment: Alignment.topCenter,
        children: [
          // Back Layer 1: Soft light blue tab
          Positioned(
            top: -10,
            left: 2,
            right: 2,
            child: Container(
              height: 24,
              decoration: BoxDecoration(
                color: const Color(0xFFD6E4FF),
                borderRadius: BorderRadius.circular(20),
              ),
            ),
          ),

          // Back Layer 2: Lilac / purple tab
          Positioned(
            top: -5,
            left: 4,
            right: 4,
            child: Container(
              height: 24,
              decoration: BoxDecoration(
                color: const Color(0xFFE2B7E5),
                borderRadius: BorderRadius.circular(20),
              ),
            ),
          ),

          // Front Layer: Bright Rose-Pink Banner Card
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 18),
            decoration: BoxDecoration(
              color: const Color(0xFFF26895),
              borderRadius: BorderRadius.circular(20),
              boxShadow: [
                BoxShadow(
                  color: const Color(0xFFF26895).withValues(alpha: 0.3),
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
                        'Start sending money tax free',
                        style: GoogleFonts.outfit(
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                          color: Colors.white,
                          letterSpacing: -0.3,
                        ),
                      ),
                      const SizedBox(height: 5),
                      Text(
                        'The best place for Africans to send\nand receive money easily!',
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

                // 3D Metallic Silver Coins Illustration
                Image.asset(
                  'assets/icons/currencies.png',
                  width: 90,
                  height: 80,
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
