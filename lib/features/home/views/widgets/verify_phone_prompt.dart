import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';
import 'package:novabanq/core/network/api_client.dart';
import 'package:novabanq/core/network/profile_api.dart';

class VerifyPhonePrompt extends StatefulWidget {
  const VerifyPhonePrompt({
    super.key,
    required this.phone,
    required this.onVerified,
  });
  final String phone;
  final VoidCallback onVerified;

  @override
  State<VerifyPhonePrompt> createState() => _VerifyPhonePromptState();
}

class _VerifyPhonePromptState extends State<VerifyPhonePrompt> {
  String? verificationId;
  String error = '';
  bool busy = false;
  bool linking = false;
  final code = TextEditingController();

  @override
  void dispose() {
    code.dispose();
    super.dispose();
  }

  Future<void> send() async {
    if (busy) return;
    setState(() {
      busy = true;
      error = '';
    });
    try {
      await FirebaseAuth.instance.verifyPhoneNumber(
        phoneNumber: widget.phone,
        verificationCompleted: link,
        verificationFailed: (failure) {
          if (mounted) {
            setState(
              () => error = failure.message ?? 'Phone verification failed.',
            );
          }
        },
        codeSent: (id, _) {
          if (mounted) setState(() => verificationId = id);
        },
        codeAutoRetrievalTimeout: (id) => verificationId = id,
      );
    } on FirebaseAuthException catch (failure) {
      if (mounted){
        setState(() => error = failure.message ?? 'Could not send code.');}
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> link(PhoneAuthCredential credential) async {
    if (!mounted || linking) return;
    setState(() {
      linking = true;
      error = '';
    });
    try {
      final user = FirebaseAuth.instance.currentUser;
      if (user == null) {
        throw const ApiFailure('AUTH_REQUIRED', 'Sign in to continue.');
      }
      await user.linkWithCredential(credential);
      await user.getIdToken(true);
      await ProfileApi(ApiClient()).verifyPhone(widget.phone);
      widget.onVerified();
      if (mounted) Navigator.of(context).pop();
    } on FirebaseAuthException catch (failure) {
      if (mounted){
        setState(() => error = failure.message ?? 'Phone verification failed.');}
    } on ApiFailure catch (failure) {
      if (mounted) setState(() => error = failure.message);
    } finally {
      if (mounted) setState(() => linking = false);
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
        Text(
          'Verify ${widget.phone}',
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
        if (verificationId == null)
          TextButton(
            onPressed: busy || linking ? null : send,
            child: const Text('Send SMS code'),
          ),
        if (verificationId != null) ...[
          TextField(
            controller: code,
            keyboardType: TextInputType.number,
            maxLength: 6,
            decoration: const InputDecoration(labelText: 'SMS code'),
          ),
          TextButton(
            onPressed: busy || linking
                ? null
                : () {
                    final id = verificationId;
                    if (id != null && code.text.length == 6) {
                      link(
                        PhoneAuthProvider.credential(
                          verificationId: id,
                          smsCode: code.text,
                        ),
                      );
                    }
                  },
            child: const Text('Verify'),
          ),
        ],
        if (busy || linking) const LinearProgressIndicator(minHeight: 2),
        if (error.isNotEmpty)
          Text(error, style: const TextStyle(color: Colors.red)),
      ],
    ),
  );
}
