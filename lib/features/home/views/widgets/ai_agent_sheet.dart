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
  const AiAgentSheet({super.key, this.api});

  final NovaApi? api;

  @override
  State<AiAgentSheet> createState() => _AiAgentSheetState();
}

class _AiAgentSheetState extends State<AiAgentSheet> {
  late final NovaApi api = widget.api ?? NovaApi(ApiClient());
  late final NovaConversationController conversation =
      NovaConversationController(api);
  final input = TextEditingController();
  final sheetController = DraggableScrollableController();
  ScrollController? sheetScrollController;

  @override
  void dispose() {
    input.dispose();
    sheetController.dispose();
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
      final controller = sheetScrollController;
      if (mounted && controller != null && controller.hasClients) {
        controller.animateTo(
          controller.position.maxScrollExtent,
          duration: const Duration(milliseconds: 180),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _expandForInput() {
    if (sheetController.isAttached) {
      sheetController.animateTo(
        1,
        duration: const Duration(milliseconds: 220),
        curve: Curves.easeOut,
      );
    }
  }

  void _resizeFromHandle(DragUpdateDetails details) {
    if (!sheetController.isAttached) return;
    final availableHeight =
        MediaQuery.sizeOf(context).height -
        MediaQuery.viewInsetsOf(context).bottom;
    if (availableHeight <= 0) return;
    final nextSize = (sheetController.size - details.delta.dy / availableHeight)
        .clamp(0.42, 1.0);
    sheetController.jumpTo(nextSize.toDouble());
  }

  @override
  Widget build(BuildContext context) {
    return DraggableScrollableSheet(
      controller: sheetController,
      initialChildSize: 0.58,
      minChildSize: 0.42,
      maxChildSize: 1,
      snap: true,

      snapSizes: const [0.58, 1],
      builder: (context, scrollController) {
        sheetScrollController = scrollController;
        return AnimatedBuilder(
          animation: sheetController,
          builder: (context, _) {
            final size = sheetController.isAttached
                ? sheetController.size
                : 0.58;
            final expansion = ((size - 0.58) / (1 - 0.58))
                .clamp(0.0, 1.0)
                .toDouble();
            final isExpanded = expansion >= 0.99;
            return Container(
              key: const ValueKey('ai-agent-sheet-surface'),
              margin: EdgeInsets.lerp(
                const EdgeInsets.only(bottom: 47, left: 40, right: 16),
                EdgeInsets.zero,
                expansion,
              ),
              padding: EdgeInsets.fromLTRB(
                16,
                12,
                16,
                MediaQuery.viewPaddingOf(context).bottom + 12,
              ),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.lerp(
                  BorderRadius.circular(16),
                  const BorderRadius.vertical(top: Radius.circular(20)),
                  expansion,
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Padding(
                    padding: EdgeInsets.only(
                      top: isExpanded ? 30 : 0,
                    ),
                    child: SizedBox(
                      height: isExpanded ? 40 : 16,
                      child: Row(
                        children: [
                          Expanded(
                            child: GestureDetector(
                              key: const ValueKey('ai-agent-sheet-handle'),
                              behavior: HitTestBehavior.opaque,
                              onVerticalDragUpdate: _resizeFromHandle,
                              child: SizedBox(
                                width: double.infinity,
                                height: 40,
                                child: Center(
                                  child: Container(
                                    width: 36,
                                    height: 4,
                                    decoration: BoxDecoration(
                                      color: const Color(0xFFD0D5DD),
                                      borderRadius: BorderRadius.circular(2),
                                    ),
                                  ),
                                ),
                              ),
                            ),
                          ),
                          if (isExpanded)
                          GestureDetector(
                            key: const ValueKey('ai-agent-sheet-close'),
                            onTap: () => Navigator.of(context).pop(),
                            child: Container(
                              margin: const EdgeInsets.only(right: 10, top: 20),
                              height: 20,
                              width: 20,
                              alignment: Alignment.center,
                              child: const Icon(Icons.close),
                            ),
                          ),

                        ],
                      ),
                    ),
                  ),
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
                              selected:
                                  conversation.mode == NovaInputMode.transfer,
                              onTap: () => conversation.selectMode(
                                NovaInputMode.transfer,
                              ),
                            ),
                            const SizedBox(width: 8),
                            AiActionButton(
                              label: 'Schedule payment',
                              selected:
                                  conversation.mode == NovaInputMode.schedule,
                              onTap: () => conversation.selectMode(
                                NovaInputMode.schedule,
                              ),
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
                        controller: scrollController,
                        physics: const AlwaysScrollableScrollPhysics(),
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
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                  ),
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
                    padding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 4,
                    ),
                    decoration: BoxDecoration(
                      color: const Color(0xFFE9ECEF),
                      borderRadius: BorderRadius.circular(24),
                    ),
                    child: Row(
                      children: [
                        Expanded(
                          child: TextField(
                            controller: input,
                            onTap: _expandForInput,
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
            );
          },
        );
      },
    );
  }
}
