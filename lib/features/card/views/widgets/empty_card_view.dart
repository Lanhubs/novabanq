import 'package:flutter/material.dart';
import 'package:get/get.dart';
import '../../controllers/card_controller.dart';
import 'add_card_primary_button.dart';
import 'card_details_top_bar.dart';
import 'empty_card_illustration.dart';
import 'empty_card_message.dart';

class EmptyCardView extends StatelessWidget {
  const EmptyCardView({super.key});

  @override
  Widget build(BuildContext context) {
    final controller = Get.isRegistered<CardController>()
        ? Get.find<CardController>()
        : Get.put(CardController());

    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 480),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          child: Column(
            children: [
              const CardDetailsTopBar(title: 'Select card'),
              Expanded(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    const EmptyCardIllustration(),
                    const SizedBox(height: 22),
                    const EmptyCardMessage(),
                    const SizedBox(height: 36),
                    AddCardPrimaryButton(
                      onTap: controller.onAddNewCard,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
