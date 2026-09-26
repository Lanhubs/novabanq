import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/core/widgets/sheet_drag_handle.dart';
import 'package:novabanq/features/auth/views/widgets/auth_cta_button.dart';

class TagCreationSuccessBottomSheet extends StatelessWidget {
  final String tag;
  final VoidCallback? onDone;

  const TagCreationSuccessBottomSheet({
    super.key,
    required this.tag,
    this.onDone,
  });

  static Future<T?> show<T>(
    BuildContext context, {
    required String tag,
    VoidCallback? onDone,
  }) {
    return showModalBottomSheet<T>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      barrierColor: Colors.black.withValues(alpha: 0.5),
      builder: (ctx) => TagCreationSuccessBottomSheet(
        tag: tag,
        onDone: onDone,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(
          top: Radius.circular(32),
        ),
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              // 1. Drag Handle
              const SheetDragHandle(),

              const SizedBox(height: 28),

              // 2. Success Check Icon
              Container(
                width: 80,
                height: 80,
                decoration: const BoxDecoration(
                  color: Color(0xFFE8F5E9),
                  shape: BoxShape.circle,
                ),
                child: const Center(
                  child: Icon(
                    Icons.check_circle_rounded,
                    size: 56,
                    color: Color(0xFF005100),
                  ),
                ),
              ),

              const SizedBox(height: 22),

              // 3. Title
              Text(
                'Account tag created',
                style: GoogleFonts.outfit(
                  fontSize: 21,
                  fontWeight: FontWeight.w700,
                  color: const Color(0xFF101828),
                  letterSpacing: -0.4,
                ),
                textAlign: TextAlign.center,
              ),

              const SizedBox(height: 8),

              // 4. Subtitle
              Text(
                'Your unique tag @$tag has been reserved. Payments are coming soon.',
                style: GoogleFonts.outfit(
                  fontSize: 13.5,
                  fontWeight: FontWeight.w400,
                  color: const Color(0xFF667085),
                  height: 1.45,
                ),
                textAlign: TextAlign.center,
              ),

              const SizedBox(height: 32),

              // 5. Done Button
              AuthCtaButton(
                text: 'Done',
                onPressed: onDone ?? () => Navigator.of(context).pop(),
              ),

              const SizedBox(height: 14),
            ],
          ),
        ),
      ),
    );
  }
}
