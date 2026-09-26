import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/core/widgets/sheet_drag_handle.dart';
import 'package:novabanq/features/auth/views/widgets/auth_cta_button.dart';

class TransactionSuccessBottomSheet extends StatelessWidget {
  final String amount;
  final String recipientName;
  final VoidCallback onDone;

  const TransactionSuccessBottomSheet({
    super.key,
    required this.amount,
    required this.recipientName,
    required this.onDone,
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
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const SheetDragHandle(),
              const SizedBox(height: 24),

              // Green check icon container
              Container(
                width: 72,
                height: 72,
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(
                    color: const Color(0xFF22C55E),
                    width: 2.5,
                  ),
                ),
                child: const Center(
                  child: Icon(
                    Icons.check_rounded,
                    size: 42,
                    color: Color(0xFF22C55E),
                  ),
                ),
              ),

              const SizedBox(height: 20),

              // Title
              Text(
                'Transaction successful',
                style: GoogleFonts.outfit(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  color: const Color(0xFF101828),
                ),
              ),

              const SizedBox(height: 8),

              // Subtitle
              Text(
                'You have successfully sent ₦ $amount to $recipientName',
                textAlign: TextAlign.center,
                style: GoogleFonts.outfit(
                  fontSize: 14,
                  fontWeight: FontWeight.w400,
                  color: const Color(0xFF667085),
                  height: 1.4,
                ),
              ),

              const SizedBox(height: 28),

              // Done Button
              AuthCtaButton(
                text: 'Done',
                onPressed: onDone,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
