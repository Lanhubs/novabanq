import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class ProfileUserHeader extends StatelessWidget {
  final String userName;
  final String tierStatus;
  final VoidCallback? onTap;

  const ProfileUserHeader({
    super.key,
    required this.userName,
    required this.tierStatus,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8.0),
        child: Row(
          children: [
            // Circular Avatar
            Container(
              width: 52,
              height: 52,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: const Color(0xFFF97316).withValues(alpha: 0.15),
                border: Border.all(
                  color: const Color(0xFFEAECF0),
                  width: 1.5,
                ),
              ),
              child: ClipOval(
                child: Image.asset(
                  'assets/images/face_scan_sample_clean.png',
                  width: 52,
                  height: 52,
                  fit: BoxFit.cover,
                  errorBuilder: (context, error, stackTrace) => const Center(
                    child: Icon(
                      Icons.person_rounded,
                      size: 28,
                      color: Color(0xFFF97316),
                    ),
                  ),
                ),
              ),
            ),

            const SizedBox(width: 14),

            // Name and Tier Info
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Flexible(
                        child: Text(
                          userName,
                          style: GoogleFonts.outfit(
                            fontSize: 17,
                            fontWeight: FontWeight.w700,
                            color: const Color(0xFF101828),
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      const SizedBox(width: 4),
                      const Icon(
                        Icons.chevron_right_rounded,
                        size: 18,
                        color: Color(0xFF101828),
                      ),
                    ],
                  ),
                  const SizedBox(height: 3),
                  Text(
                    tierStatus,
                    style: GoogleFonts.outfit(
                      fontSize: 12.5,
                      fontWeight: FontWeight.w500,
                      color: const Color(0xFF16A34A),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
