import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class ProfileSectionHeader extends StatelessWidget {
  final String title;

  const ProfileSectionHeader({
    super.key,
    required this.title,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 20.0, bottom: 8.0),
      child: Text(
        title,
        style: GoogleFonts.outfit(
          fontSize: 13.5,
          fontWeight: FontWeight.w700,
          color: const Color(0xFF101828),
        ),
      ),
    );
  }
}
