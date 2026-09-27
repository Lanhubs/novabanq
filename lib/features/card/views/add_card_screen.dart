import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:novabanq/features/auth/views/widgets/auth_cta_button.dart';
// import 'package:novabanq/features/card/views/card_details_screen.dart';
import 'package:novabanq/features/card/views/widgets/card_created_successfully.dart';
import 'widgets/card_details_top_bar.dart';
import 'widgets/card_type_option.dart';

class AddCardScreen extends StatefulWidget {
  const AddCardScreen({super.key});

  @override
  State<AddCardScreen> createState() => _AddCardScreenState();
}

class _AddCardScreenState extends State<AddCardScreen> {
  String? selectedType;

  void continueWithSelection() {
    final type = selectedType;
    if (type == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Select a card type to continue.')),
      );
      return;
    }
    Get.to(const CardCreatedSuccessfully());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
              child: Column(
                children: [
                  const CardDetailsTopBar(title: 'Add a card'),
                  const SizedBox(height: 28),
                  CardTypeOption(
                    title: 'Virtual card',
                    subtitle: 'Local online payment',
                    selected: selectedType == 'virtual',
                    onTap: () => setState(() => selectedType = 'virtual'),
                  ),
                  const SizedBox(height: 20),
                  CardTypeOption(
                    title: 'Physical card',
                    subtitle: 'Delivered to your doorstep',
                    selected: selectedType == 'physical',
                    onTap: () => setState(() => selectedType = 'physical'),
                  ),
                  const Spacer(),
                  SizedBox(
                    width: double.infinity,
                    height: 56,
                    child: AuthCtaButton(
                      text: 'Continue',
                      onPressed: continueWithSelection,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
