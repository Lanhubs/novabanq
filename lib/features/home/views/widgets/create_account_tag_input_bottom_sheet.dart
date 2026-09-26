import 'dart:async';
import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/core/network/api_client.dart';
import 'package:novabanq/core/network/profile_api.dart';
import 'package:novabanq/core/widgets/sheet_drag_handle.dart';
import 'package:novabanq/features/auth/views/widgets/auth_cta_button.dart';
import '../../controllers/home_controller.dart';
import 'tag_creation_success_bottom_sheet.dart';
import 'tag_error_text.dart';
import 'tag_input_field.dart';

class CreateAccountTagInputBottomSheet extends StatefulWidget {
  const CreateAccountTagInputBottomSheet({super.key, this.onTagCreated});
  final ValueChanged<String>? onTagCreated;

  static Future<T?> show<T>(
    BuildContext context, {
    ValueChanged<String>? onTagCreated,
  }) => showModalBottomSheet<T>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    barrierColor: Colors.black.withValues(alpha: 0.5),
    builder: (_) =>
        CreateAccountTagInputBottomSheet(onTagCreated: onTagCreated),
  );

  @override
  State<CreateAccountTagInputBottomSheet> createState() => _TagSheetState();
}

class _TagSheetState extends State<CreateAccountTagInputBottomSheet> {
  final input = TextEditingController();
  Timer? debounce;
  String error = '';
  String preview = '';
  bool checking = false;
  bool submitting = false;
  int requestVersion = 0;

  @override
  void dispose() {
    debounce?.cancel();
    input.dispose();
    super.dispose();
  }

  void validate(String value) {
    debounce?.cancel();
    final version = ++requestVersion;
    final base = value.trim().toLowerCase();
    setState(() {
      preview = '';
      checking = false;
      error =
          base.length < 3 ||
              base.length > 25 ||
              !RegExp(r'^[a-z0-9_]+$').hasMatch(base)
          ? 'Use 3–25 letters, numbers or underscores.'
          : '';
    });
    if (error.isNotEmpty) return;
    debounce = Timer(const Duration(milliseconds: 400), () async {
      setState(() => checking = true);
      try {
        final data = await ProfileApi(ApiClient()).checkTag(base);
        if (data['available'] != true) {
          throw const ApiFailure('TAG_TAKEN', 'Tag is already taken.');
        }
        final tag = data['tag']?.toString() ?? base;
        if (mounted && version == requestVersion) {
          setState(() => preview = '@$tag');
        }
      } on ApiFailure catch (failure) {
        if (mounted && version == requestVersion) {
          setState(() => error = failure.message);
        }
      } finally {
        if (mounted && version == requestVersion) {
          setState(() => checking = false);
        }
      }
    });
  }

  Future<void> submit() async {
    if (submitting || checking || error.isNotEmpty || preview.isEmpty) return;
    setState(() => submitting = true);
    try {
      final data = await ProfileApi(
        ApiClient(),
      ).claimTag(input.text.trim().toLowerCase());
      final tag = data['tag']?.toString() ?? '';
      if (Get.isRegistered<HomeController>())
        Get.find<HomeController>().loadProfile();
      widget.onTagCreated?.call(tag);
      if (!mounted) return;
      Navigator.of(context).pop(tag);
      if (Get.context != null)
        TagCreationSuccessBottomSheet.show(Get.context!, tag: tag);
    } on ApiFailure catch (failure) {
      if (mounted) setState(() => error = failure.message);
    } finally {
      if (mounted) setState(() => submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) => Container(
    decoration: const BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.vertical(top: Radius.circular(32)),
    ),
    child: SafeArea(
      top: false,
      child: Padding(
        padding: EdgeInsets.only(
          left: 24,
          right: 24,
          top: 12,
          bottom: MediaQuery.viewInsetsOf(context).bottom + 16,
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Center(child: SheetDragHandle()),
              const SizedBox(height: 24),
              Center(
                child: Text(
                  'Create account @tag',
                  textAlign: TextAlign.center,
                  style: GoogleFonts.outfit(
                    fontSize: 21,
                    fontWeight: FontWeight.w700,
                    color: const Color(0xFF101828),
                  ),
                ),
              ),
              const SizedBox(height: 8),
              Center(
                child: Text(
                    'Create a unique tag for your Novabanq\nprofile.',
                  textAlign: TextAlign.center,
                  style: GoogleFonts.outfit(
                    fontSize: 13.5,
                    color: const Color(0xFF667085),
                  ),
                ),
              ),
              const SizedBox(height: 28),
              Text(
                'Username',
                style: GoogleFonts.outfit(
                  fontSize: 14.5,
                  fontWeight: FontWeight.w600,
                  color: const Color(0xFF101828),
                ),
              ),
              const SizedBox(height: 8),
              TagInputField(
                controller: input,
                hasError: error.isNotEmpty,
                onChanged: validate,
              ),
              if (error.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: TagErrorText(message: error),
                ),
              if (checking)
                const Padding(
                  padding: EdgeInsets.only(top: 6),
                  child: LinearProgressIndicator(minHeight: 2),
                ),
              if (preview.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text(
                    'Your tag will be $preview',
                    style: const TextStyle(color: Color(0xFF005100)),
                  ),
                ),
              const SizedBox(height: 32),
              AuthCtaButton(
                text: submitting ? 'Creating...' : 'Continue',
                onPressed: submit,
              ),
              const SizedBox(height: 8),
            ],
          ),
        ),
      ),
    ),
  );
}
