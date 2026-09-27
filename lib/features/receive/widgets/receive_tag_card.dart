import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'tag_action_item.dart';

class ReceiveTagCard extends StatelessWidget {
  final String tag;
  final VoidCallback onCopyTag;
  final VoidCallback onShareLink;

  const ReceiveTagCard({
    super.key,
    required this.tag,
    required this.onCopyTag,
    required this.onShareLink,
  });

  @override
  Widget build(BuildContext context) {
    final displayTag = tag.startsWith('@') ? tag : '@$tag';

    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        color: Color(0x21E7E9EC),
        borderRadius: BorderRadius.circular(16),
      ),
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Your account @tag',
            style: GoogleFonts.outfit(
              fontSize: 14,
              fontWeight: FontWeight.w700,
              color: const Color(0xFF101828),
            ),
          ),
          const SizedBox(height: 10),
          Text(
            displayTag,
            style: GoogleFonts.outfit(
              fontSize: 22,
              fontWeight: FontWeight.w700,
              color: const Color(0xFF005100),
              letterSpacing: -0.3,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            'Share this so anyone in Africa can pay you',
            style: GoogleFonts.outfit(
              fontSize: 13,
              fontWeight: FontWeight.w400,
              color: const Color(0xFF667085),
            ),
          ),
          const SizedBox(height: 18),
          Row(
            children: [
              TagActionItem(
                icon: Icons.copy_rounded,
                label: 'Copy @tag',
                onTap: onCopyTag,
              ),
              const SizedBox(width: 24),
              TagActionItem(
                icon: Icons.share_outlined,
                label: 'Share link',
                onTap: onShareLink,
              ),
            ],
          ),
        ],
      ),
    );
  }
}
