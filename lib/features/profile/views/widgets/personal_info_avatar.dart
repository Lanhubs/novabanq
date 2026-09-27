import 'package:flutter/material.dart';

class PersonalInfoAvatar extends StatelessWidget {
  final VoidCallback onTap;

  const PersonalInfoAvatar({
    super.key,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: GestureDetector(
        onTap: onTap,
        child: SizedBox(
          width: 80,
          height: 80,
          child: Stack(
            alignment: Alignment.center,
            children: [
              // Main Circular Avatar
              Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: const Color(0xFFF97316).withValues(alpha: 0.2),
                  border: Border.all(
                    color: const Color(0xFFF97316),
                    width: 2.0,
                  ),
                ),
                child: ClipOval(
                  child: Image.asset(
                    'assets/images/face_scan_sample_clean.png',
                    width: 80,
                    height: 80,
                    fit: BoxFit.cover,
                    errorBuilder: (context, error, stackTrace) => const Center(
                      child: Icon(
                        Icons.person_rounded,
                        size: 40,
                        color: Color(0xFFF97316),
                      ),
                    ),
                  ),
                ),
              ),

              // Camera Icon Overlay Badge at the bottom
              Positioned(
                bottom: 2,
                child: Container(
                  width: 28,
                  height: 22,
                  decoration: BoxDecoration(
                    color: Colors.black.withValues(alpha: 0.6),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: const Center(
                    child: Icon(
                      Icons.photo_camera_rounded,
                      size: 14,
                      color: Colors.white,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
