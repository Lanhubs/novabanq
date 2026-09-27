import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:novabanq/features/card/views/add_card_screen.dart';
import 'package:novabanq/features/card/views/widgets/card_type_option.dart';

void main() {
  testWidgets('Add card offers both types and requires a selection', (
    tester,
  ) async {
    await tester.pumpWidget(const MaterialApp(home: AddCardScreen()));
    expect(find.text('Add a card'), findsOneWidget);
    expect(find.text('Virtual card'), findsOneWidget);
    expect(find.text('Physical card'), findsOneWidget);

    await tester.tap(find.text('Continue'));
    await tester.pump();
    expect(find.text('Select a card type to continue.'), findsOneWidget);

    await tester.tap(find.text('Virtual card'));
    await tester.pump();
    final options = tester
        .widgetList<CardTypeOption>(find.byType(CardTypeOption))
        .toList();
    expect(options.first.selected, isTrue);
    expect(options.last.selected, isFalse);
  });
}
