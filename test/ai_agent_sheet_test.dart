import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:novabanq/core/network/api_client.dart';
import 'package:novabanq/core/network/nova_api.dart';
import 'package:novabanq/features/home/controllers/nova_conversation_controller.dart';
import 'package:novabanq/features/home/views/widgets/ai_agent_sheet.dart';
import 'package:novabanq/features/home/views/widgets/nova_message_bubble.dart';

void main() {
  testWidgets('assistant and sender bubbles have mirrored bottom corners', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Column(
          children: [
            NovaMessageBubble(message: NovaMessage('Assistant reply')),
            NovaMessageBubble(
              message: NovaMessage('Sender reply', isUser: true),
            ),
          ],
        ),
      ),
    );

    final bubbles = tester.widgetList<Container>(find.byType(Container));
    final bubbleDecorations = bubbles
        .map((container) => container.decoration)
        .whereType<BoxDecoration>()
        .where((decoration) => decoration.borderRadius != null)
        .toList();

    expect(bubbleDecorations, hasLength(2));
    expect(
      bubbleDecorations[0].borderRadius,
      const BorderRadius.only(
        topLeft: Radius.circular(16),
        topRight: Radius.circular(16),
        bottomRight: Radius.circular(16),
      ),
    );
    expect(
      bubbleDecorations[1].borderRadius,
      const BorderRadius.only(
        topLeft: Radius.circular(16),
        topRight: Radius.circular(16),
        bottomLeft: Radius.circular(16),
      ),
    );
  });

  testWidgets('tapping the composer expands the AI sheet', (tester) async {
    tester.view.physicalSize = const Size(400, 800);
    tester.view.devicePixelRatio = 1;
    tester.view.viewPadding = const FakeViewPadding(top: 32);
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetViewPadding);

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: AiAgentSheet(
            api: NovaApi(ApiClient(tokenProvider: (_) async => 'test-token')),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    final greeting = find.text('Hi, what would you like to do?');
    final surface = find.byKey(const ValueKey('ai-agent-sheet-surface'));
    final paintedSurface = find
        .descendant(of: surface, matching: find.byType(DecoratedBox))
        .first;
    final compactRect = tester.getRect(paintedSurface);
    expect(compactRect.left, closeTo(40, 1));
    expect(compactRect.right, closeTo(384, 1));
    expect(compactRect.bottom, closeTo(753, 1));

    final compactTop = tester.getTopLeft(greeting).dy;
    await tester.drag(
      find.byKey(const ValueKey('ai-agent-sheet-handle')),
      const Offset(0, -180),
    );
    await tester.pumpAndSettle();
    final draggedTop = tester.getTopLeft(greeting).dy;
    expect(draggedTop, lessThan(compactTop));

    await tester.tap(find.byType(TextField));
    await tester.pumpAndSettle();

    expect(tester.getTopLeft(greeting).dy, lessThan(draggedTop));
    final expandedRect = tester.getRect(paintedSurface);
    expect(expandedRect.left, closeTo(0, 1));
    expect(expandedRect.right, closeTo(400, 1));
    expect(expandedRect.bottom, closeTo(800, 1));
    final closeButton = find.byKey(const ValueKey('ai-agent-sheet-close'));
    expect(closeButton, findsOneWidget);
    expect(tester.getTopLeft(closeButton).dy, greaterThanOrEqualTo(42));
    final handleRect = tester.getRect(
      find.byKey(const ValueKey('ai-agent-sheet-handle')),
    );
    expect(handleRect.top, greaterThanOrEqualTo(42));
    expect(tester.getTopLeft(greeting).dy, greaterThan(handleRect.bottom));
  });

  testWidgets('the expanded AI sheet can be closed', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (context) => TextButton(
              onPressed: () => showModalBottomSheet<void>(
                context: context,
                isScrollControlled: true,
                backgroundColor: Colors.transparent,
                builder: (_) => AiAgentSheet(
                  api: NovaApi(
                    ApiClient(tokenProvider: (_) async => 'test-token'),
                  ),
                ),
              ),
              child: const Text('Open AI assistant'),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Open AI assistant'));
    await tester.pumpAndSettle();
    await tester.tap(find.byType(TextField));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const ValueKey('ai-agent-sheet-close')));
    await tester.pumpAndSettle();

    expect(find.byKey(const ValueKey('ai-agent-sheet-surface')), findsNothing);
  });
}
