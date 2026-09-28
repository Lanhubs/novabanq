import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:novabanq/features/home/views/widgets/nova_schedule_date_sheet.dart';

void main() {
  testWidgets('schedule sheet requires an explicit time', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: TextButton(
              onPressed: () => showModalBottomSheet<void>(
                context: context,
                isScrollControlled: true,
                builder: (sheetContext) => const NovaScheduleDateSheet(),
              ),
              child: const Text('Open schedule sheet'),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('Open schedule sheet'));
    await tester.pumpAndSettle();

    expect(find.byType(CalendarDatePicker), findsOneWidget);
    expect(find.text('Date'), findsOneWidget);
    expect(find.text('Select time'), findsOneWidget);
    final continueButton = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'Continue'),
    );
    expect(continueButton.onPressed, isNull);
  });
}
