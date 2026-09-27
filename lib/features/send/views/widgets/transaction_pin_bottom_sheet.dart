import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/core/widgets/custom_numeric_keypad.dart';
import 'package:novabanq/core/widgets/sheet_drag_handle.dart';
import 'package:novabanq/features/auth/views/widgets/auth_cta_button.dart';
import 'package:novabanq/features/auth/views/widgets/pin_code_display.dart';

class TransactionPinBottomSheet extends StatelessWidget {
  final String pin;
  final ValueChanged<String> onKeyPress;
  final VoidCallback onBackspace;
  final VoidCallback? onClear;
  final VoidCallback onConfirm;
  final bool isLoading;

  const TransactionPinBottomSheet({
    super.key,
    required this.pin,
    required this.onKeyPress,
    required this.onBackspace,
    this.onClear,
    required this.onConfirm,
    this.isLoading = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: SafeArea(
        top: false,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 12),
            const SheetDragHandle(),
            const SizedBox(height: 12),

            // Title
            Text(
              'Enter your PIN',
              style: GoogleFonts.outfit(
                fontSize: 20,
                fontWeight: FontWeight.w700,
                color: const Color(0xFF101828),
              ),
            ),

            const SizedBox(height: 6),

            // Subtitle
            Text(
              'Enter your 5-digit PIN to confirm this transaction',
              textAlign: TextAlign.center,
              style: GoogleFonts.outfit(
                fontSize: 13,
                fontWeight: FontWeight.w400,
                color: const Color(0xFF667085),
              ),
            ),

            const SizedBox(height: 20),

            // 5-Digit PIN Display
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20.0),
              child: PinCodeDisplay(
                pin: pin,
                length: 5,
                obscure: true,
              ),
            ),

            const SizedBox(height: 20),

            // Confirm Button
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20.0),
              child: AuthCtaButton(
                text: isLoading ? 'Confirming...' : 'Confirm',
                onPressed: isLoading ? () {} : onConfirm,
              ),
            ),

            const SizedBox(height: 16),

            // Custom Keypad
            CustomNumericKeypad(
              onKeyPress: onKeyPress,
              onBackspace: onBackspace,
              onClear: onClear,
            ),
          ],
        ),
      ),
    );
  }
}
