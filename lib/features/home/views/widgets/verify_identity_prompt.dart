import 'package:flutter/material.dart';
import 'package:novabanq/core/network/api_client.dart';
import 'package:novabanq/core/network/identity_service.dart';
import 'package:novabanq/core/network/profile_api.dart';

class VerifyIdentityPrompt extends StatefulWidget {
  const VerifyIdentityPrompt({super.key, required this.onVerified});
  final VoidCallback onVerified;

  @override
  State<VerifyIdentityPrompt> createState() => _VerifyIdentityPromptState();
}

class _VerifyIdentityPromptState extends State<VerifyIdentityPrompt> {
  final bvn = TextEditingController();
  bool busy = false;
  String error = '';

  @override
  void dispose() {
    bvn.dispose();
    super.dispose();
  }

  Future<void> verify() async {
    if (busy) return;
    setState(() {
      busy = true;
      error = '';
    });
    try {
      final result = await IdentityService(
        ProfileApi(ApiClient()),
      ).verifyWithCamera(bvn.text.trim());
      if (result['status'] == 'VERIFIED') {
        widget.onVerified();
        if (mounted) Navigator.of(context).pop();
      } else if (mounted) {
        setState(
          () => error = 'Identity check: ${result['status'] ?? 'REJECTED'}',
        );
      }
    } on ApiFailure catch (failure) {
      if (failure.code == 'IDENTITY_ALREADY_VERIFIED') {
        widget.onVerified();
        if (mounted) Navigator.of(context).pop();
      } else if (mounted) {
        setState(() => error = failure.message);
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Padding(
    padding: EdgeInsets.fromLTRB(
      20,
      24,
      20,
      MediaQuery.viewInsetsOf(context).bottom + 24,
    ),
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Text(
          'Verify identity',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
        TextField(
          controller: bvn,
          keyboardType: TextInputType.number,
          maxLength: 11,
          decoration: const InputDecoration(labelText: '11-digit BVN'),
        ),
        TextButton(
          onPressed: busy ? null : verify,
          child: const Text('Capture selfie and verify'),
        ),
        if (busy) const LinearProgressIndicator(minHeight: 2),
        if (error.isNotEmpty)
          Text(error, style: const TextStyle(color: Colors.red)),
      ],
    ),
  );
}
