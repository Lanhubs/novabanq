import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/core/widgets/sheet_drag_handle.dart';
import 'package:novabanq/features/auth/views/widgets/auth_cta_button.dart';
import 'account_tag_alert_icon.dart';
import 'account_tag_dismiss_button.dart';
import 'create_account_tag_input_bottom_sheet.dart';

class CreateAccountTagBottomSheet extends StatelessWidget {
  final VoidCallback? onCreateTag;
  final VoidCallback? onDismiss;

  const CreateAccountTagBottomSheet({
    super.key,
    this.onCreateTag,
    this.onDismiss,
  });

  static Future<T?> show<T>(
    BuildContext context, {
    VoidCallback? onCreateTag,
    VoidCallback? onDismiss,
  }) {
    return showModalBottomSheet<T>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      barrierColor: Colors.black.withValues(alpha: 0.5),
      builder: (ctx) => CreateAccountTagBottomSheet(
        onCreateTag: onCreateTag,
        onDismiss: onDismiss,
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
              // 1. Top Drag Handle
              const SheetDragHandle(),

              const SizedBox(height: 28),

              // 2. Alert Triangle Icon
              const AccountTagAlertIcon(),

              const SizedBox(height: 22),

              // 3. Title
              Text(
                'Create your account tag',
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
                'You need to create your account tag for easy\ntransactions on Novabanq',
                style: GoogleFonts.outfit(
                  fontSize: 13.5,
                  fontWeight: FontWeight.w400,
                  color: const Color(0xFF667085),
                  height: 1.45,
                ),
                textAlign: TextAlign.center,
              ),

              const SizedBox(height: 30),

              // 5. Primary Reusable CTA Button
              AuthCtaButton(
                text: 'Create tag',
                onPressed: onCreateTag ??
                    () {
                      Navigator.of(context).pop();
                      CreateAccountTagInputBottomSheet.show(context);
                    },
              ),

              const SizedBox(height: 14),

              // 6. Secondary "Not now" button
              AccountTagDismissButton(
                onDismiss: onDismiss ?? () => Navigator.of(context).pop(),
              ),

              const SizedBox(height: 8),
            ],
          ),
        ),
      ),
    );
  }
}
