import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get/get.dart';
import 'package:novabanq/features/auth/controllers/login_controller.dart';
import 'package:novabanq/features/auth/views/login_screen.dart';

void main() {
  testWidgets('login shows both fields and validates missing credentials', (
    tester,
  ) async {
    Get.testMode = true;
    await tester.binding.setSurfaceSize(const Size(392, 466));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final controller = Get.put(LoginController());
    await tester.pumpWidget(const GetMaterialApp(home: LoginScreen()));

    expect(find.text('Welcome back'), findsOneWidget);
    expect(find.text('Email address'), findsOneWidget);
    expect(find.text('Password'), findsOneWidget);
    expect(find.text('Forgot password?'), findsOneWidget);
    expect(find.text('Sign up'), findsOneWidget);

    await tester.tap(find.text('Continue'));
    await tester.pump();
    expect(controller.error.value, 'Enter your email address and password.');
    expect(find.text(controller.error.value), findsOneWidget);
    Get.delete<LoginController>();
  });
}
