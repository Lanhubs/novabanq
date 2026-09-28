import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:hugeicons/hugeicons.dart';
import 'package:novabanq/core/network/api_client.dart';
import 'package:novabanq/core/network/nova_api.dart';
import 'package:novabanq/features/home/controllers/nova_conversation_controller.dart';
import 'package:novabanq/features/home/controllers/nova_transfer_flow.dart';
import 'ai_action_button.dart';
import 'nova_message_bubble.dart';
import 'nova_schedule_date_sheet.dart';

class AiAgentSheet extends StatefulWidget {
  const AiAgentSheet({super.key});

  @override
  State<AiAgentSheet> createState() => _AiAgentSheetState();
}

class _AiAgentSheetState extends State<AiAgentSheet> {
  late final NovaApi api = NovaApi(ApiClient());
  late final NovaConversationController conversation =
      NovaConversationController(api);
  final input = TextEditingController();
  final scroll = ScrollController();

  @override
  void dispose() {
    input.dispose();
    scroll.dispose();
    conversation.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    if (conversation.isBusy) return;
    final message = input.text.trim();
    if (message.isEmpty) return;
    input.clear();
    var preview = await conversation.submit(message);
    if (!mounted) return;
    _scrollToLatest();
    if (preview != null &&
        conversation.mode == NovaInputMode.schedule &&
        !preview.isScheduled) {
      final scheduleAt = await showModalBottomSheet<DateTime>(
        context: context,
        isScrollControlled: true,
        useSafeArea: true,
        backgroundColor: Colors.transparent,
        builder: (sheetContext) => const NovaScheduleDateSheet(),
      );
      if (!mounted || scheduleAt == null) return;
      preview = await conversation.submit(message, scheduleAt: scheduleAt);
      if (!mounted) return;
      _scrollToLatest();
    }
    if (preview != null) {
      await NovaTransferFlow.confirm(context, preview, api, conversation);
    }
  }

  void _scrollToLatest() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && scroll.hasClients) {
        scroll.animateTo(
          scroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 180),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.sizeOf(context);
    final keyboard = MediaQuery.viewInsetsOf(context).bottom;
    return AnimatedPadding(
      duration: const Duration(milliseconds: 180),
      padding: EdgeInsets.only(bottom: keyboard),
      child: Container(
        margin: const EdgeInsets.only(bottom: 47, left: 40, right: 16),
        padding: const EdgeInsets.all(16),
        height: math.min(
          size.height * 0.62,
          math.max(0, size.height - keyboard - 80),
        ),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const NovaMessageBubble(
              message: NovaMessage('Hi, what would you like to do?'),
            ),
            const SizedBox(height: 10),
            Padding(
              padding: const EdgeInsets.only(left: 44),
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: AnimatedBuilder(
                  animation: conversation,
                  builder: (context, _) => Row(
                    children: [
                      AiActionButton(
                        label: 'Send money',
                        selected: conversation.mode == NovaInputMode.transfer,
                        onTap: () =>
                            conversation.selectMode(NovaInputMode.transfer),
                      ),
                      const SizedBox(width: 8),
                      AiActionButton(
                        label: 'Schedule payment',
                        selected: conversation.mode == NovaInputMode.schedule,
                        onTap: () =>
                            conversation.selectMode(NovaInputMode.schedule),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Expanded(
              child: AnimatedBuilder(
                animation: conversation,
                builder: (context, _) => ListView.builder(
                  controller: scroll,
                  itemCount:
                      conversation.messages.length +
                      (conversation.isBusy ? 1 : 0),
                  itemBuilder: (context, index) {
                    if (index == conversation.messages.length) {
                      return const Padding(
                        padding: EdgeInsets.all(12),
                        child: Align(
                          alignment: Alignment.centerLeft,
                          child: SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          ),
                        ),
                      );
                    }
                    return NovaMessageBubble(
                      message: conversation.messages[index],
                    );
                  },
                ),
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
              decoration: BoxDecoration(
                color: const Color(0xFFE9ECEF),
                borderRadius: BorderRadius.circular(24),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: input,
                      maxLength: 500,
                      minLines: 1,
                      maxLines: 3,
                      textInputAction: TextInputAction.send,
                      onSubmitted: (_) => _send(),
                      decoration: InputDecoration(
                        hintText: 'Type your message',
                        hintStyle: GoogleFonts.outfit(
                          color: Colors.black54,
                          fontSize: 14,
                        ),
                        border: InputBorder.none,
                        isDense: true,
                        counterText: '',
                      ),
                    ),
                  ),
                  AnimatedBuilder(
                    animation: conversation,
                    builder: (context, _) => IconButton(
                      onPressed: conversation.isBusy ? null : _send,
                      icon: const HugeIcon(
                        icon: HugeIcons.strokeRoundedSent,
                        color: Colors.black87,
                        size: 20,
                      ),
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
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
