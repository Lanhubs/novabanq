import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:novabanq/features/home/views/widgets/home_balance_section.dart';

void main() {
  testWidgets('shows a balance skeleton until the account has loaded', (
    tester,
  ) async {
    final semantics = tester.ensureSemantics();

    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: HomeBalanceSection(
            balance: '—',
            isLoading: true,
            isVisible: true,
            currencyCode: 'NGN',
            countryCode: 'NG',
            currencySymbol: '₦',
            onToggleVisibility: _noop,
          ),
        ),
      ),
    );

    expect(find.bySemanticsLabel('Loading account balance'), findsOneWidget);
    expect(find.text('—'), findsNothing);
    expect(find.text('NGN'), findsOneWidget);

    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: HomeBalanceSection(
            balance: '1,234.56',
            isLoading: false,
            isVisible: true,
            currencyCode: 'NGN',
            countryCode: 'NG',
            currencySymbol: '₦',
            onToggleVisibility: _noop,
          ),
        ),
      ),
    );

    expect(find.text('1,234.56'), findsOneWidget);
    semantics.dispose();
  });
}

void _noop() {}
