import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/features/home/controllers/nova_conversation_controller.dart';

class NovaMessageBubble extends StatelessWidget {
  const NovaMessageBubble({super.key, required this.message});
  final NovaMessage message;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        mainAxisAlignment: message.isUser
            ? MainAxisAlignment.end
            : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!message.isUser) ...[
            Image.asset(
              'assets/icons/receiver_icon.png',
              width: 36,
              height: 36,
            ),
            const SizedBox(width: 8),
          ],
          Flexible(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              decoration: BoxDecoration(
                color: message.isUser
                    ? const Color(0xFF005100)
                    : message.isError
                    ? const Color(0xFFFFE5E5)
                    : const Color(0xFFA7E3BB),
                borderRadius: BorderRadius.circular(16),
              ),
              child: Text(
                message.text,
                style: GoogleFonts.outfit(
                  fontSize: message.isUser ? 12 : 14,
                  color: message.isUser ? Colors.white : Colors.black87,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
          ),
          if (message.isUser) ...[
            const SizedBox(width: 8),
            Image.asset('assets/icons/sender_icon.png', width: 36, height: 36),
          ],
        ],
      ),
    );
  }
}
