import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:hugeicons/hugeicons.dart';
import 'user_avatar_widget.dart';

class HomeTopBar extends StatelessWidget {
  final String userName;
  final String? accountTag;
  final VoidCallback onNotificationTap;
  final VoidCallback onAddAccountTagTap;

  const HomeTopBar({
    super.key,
    required this.userName,
    this.accountTag,
    required this.onNotificationTap,
    required this.onAddAccountTagTap,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        // 1. User Avatar
        const UserAvatarWidget(size: 50),

        const SizedBox(width: 14),

        // 2. Greeting & Account Tag Alert
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'Good Morning $userName!',
                style: GoogleFonts.outfit(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  color: const Color(0xFF101828),
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 3),
              GestureDetector(
                onTap: onAddAccountTagTap,
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (accountTag != null && accountTag!.isNotEmpty) ...[
                      const Icon(
                        Icons.verified_rounded,
                        size: 15,
                        color: Color(0xFF005100),
                      ),
                      const SizedBox(width: 4),
                      Text(
                        '@$accountTag',
                        style: GoogleFonts.outfit(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: const Color(0xFF005100),
                        ),
                      ),
                    ] else ...[
                      const Icon(
                        Icons.warning_amber_rounded,
                        size: 16,
                        color: Color(0xFFEAB308),
                      ),
                      const SizedBox(width: 5),
                      Text(
                        'Add a account tag',
                        style: GoogleFonts.outfit(
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
                          color: const Color(0xFFEAB308),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),

        const SizedBox(width: 8),

        // 3. Circular Notification Bell Button
        InkWell(
          onTap: onNotificationTap,
          borderRadius: BorderRadius.circular(24),
          child: Container(
            width: 48,
            height: 48,
            decoration: const BoxDecoration(
              color: Color(0xFFF2F4F7),
              shape: BoxShape.circle,
            ),
            child: const Center(
              child: HugeIcon(
                icon: HugeIcons.strokeRoundedNotification02,
                color: Color(0xFF101828),
                size: 24,
              ),
            ),
          ),
        ),
      ],
    );
  }
}
