import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class VirtualCardBack extends StatelessWidget {
  final String cvv;
  final String contactNumber;

  const VirtualCardBack({
    super.key,
    required this.cvv,
    this.contactNumber = '01-345-782-901',
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      height: 180,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Color(0xFF50C878),
            Color(0xFFA7E3BB),
          ],
        ),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF50C878).withValues(alpha: 0.25),
            blurRadius: 14,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 1. Top Customer Support Contact Text
          Padding(
            padding: const EdgeInsets.only(left: 16, right: 16, top: 12, bottom: 8),
            child: Text(
              'Customer center contact number: $contactNumber',
              style: GoogleFonts.outfit(
                fontSize: 10,
                fontWeight: FontWeight.w500,
                color: Colors.white.withValues(alpha: 0.95),
              ),
            ),
          ),

          // 2. Black/Dark Green Magnetic Stripe across the card
          Container(
            width: double.infinity,
            height: 34,
            color: const Color(0xFF023616),
          ),

          const SizedBox(height: 10),

          // 3. Signature & CVV box + Disclaimer Text
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Signature / CVV strip
                Container(
                  width: 180,
                  height: 30,
                  decoration: BoxDecoration(
                    color: const Color(0xFFFFFDF8),
                    borderRadius: BorderRadius.circular(3),
                  ),
                  child: Stack(
                    alignment: Alignment.center,
                    children: [
                      // Security hatch lines inside signature strip
                      Column(
                        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                        children: List.generate(
                          5,
                          (_) => Container(
                            height: 1,
                            color: const Color(0xFFE5E0D0),
                          ),
                        ),
                      ),
                      // CVV number on the right
                      Positioned(
                        right: 8,
                        child: Text(
                          cvv,
                          style: GoogleFonts.caveat(
                            fontSize: 15,
                            fontWeight: FontWeight.w700,
                            fontStyle: FontStyle.italic,
                            color: const Color(0xFF101828),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 8),

                // Disclaimer terms
                Text(
                  'faucibus sollicitudin, odio non Cras ac sapien ullamcorper diam vitae risus Nunc placerat, placerat. id risus tincidunt Vestibulum odio Donec non Morbi nisi',
                  style: GoogleFonts.outfit(
                    fontSize: 8.2,
                    fontWeight: FontWeight.w400,
                    color: Colors.white.withValues(alpha: 0.8),
                    height: 1.25,
                  ),
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
