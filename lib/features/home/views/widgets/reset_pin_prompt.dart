import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';
import 'package:novabanq/core/network/api_client.dart';
import 'package:novabanq/core/network/profile_api.dart';

class ResetPinPrompt extends StatefulWidget {
  const ResetPinPrompt({super.key, required this.phone, required this.onSaved});
  final String phone;
  final VoidCallback onSaved;

  @override
  State<ResetPinPrompt> createState() => _ResetPinPromptState();
}

class _ResetPinPromptState extends State<ResetPinPrompt> {
  final sms = TextEditingController();
  final pin = TextEditingController();
  String? verificationId;
  bool busy = false;
  bool resetDone = false;
  String error = '';

  @override
  void dispose() {
    sms.dispose();
    pin.dispose();
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
        verificationCompleted: confirmCredential,
        verificationFailed: (failure) {
          if (mounted) {
            setState(
              () => error = failure.message ?? 'SMS verification failed.',
            );
          }
        },
        codeSent: (id, _) {
          if (mounted) setState(() => verificationId = id);
        },
        codeAutoRetrievalTimeout: (id) => verificationId = id,
      );
    } on FirebaseAuthException catch (failure) {
      if (mounted) {
        setState(() => error = failure.message ?? 'Could not send code.');
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> confirmCredential(PhoneAuthCredential credential) async {
    if (!mounted) return;
    setState(() {
      busy = true;
      error = '';
    });
    try {
      final user = FirebaseAuth.instance.currentUser;
      if (user == null) {
        throw const ApiFailure('AUTH_REQUIRED', 'Sign in to continue.');
      }
      if (user.phoneNumber == widget.phone) {
        await user.reauthenticateWithCredential(credential);
      } else {
        await user.linkWithCredential(credential);
      }
      await user.getIdToken(true);
      await ProfileApi(ApiClient()).resetPin();
      resetDone = true;
      await savePin();
    } on FirebaseAuthException catch (failure) {
      if (mounted) {
        setState(() => error = failure.message ?? 'Phone verification failed.');
      }
    } on ApiFailure catch (failure) {
      if (mounted) setState(() => error = failure.message);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> savePin() async {
    if (!RegExp(r'^\d{5}$').hasMatch(pin.text)) {
      if (mounted) setState(() => error = 'Enter a new 5-digit PIN.');
      return;
    }
    try {
      await ProfileApi(ApiClient()).setPin(pin.text);
      pin.clear();
      widget.onSaved();
      if (mounted) Navigator.of(context).pop();
    } on ApiFailure catch (failure) {
      if (mounted) setState(() => error = failure.message);
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
          'Reset transaction PIN',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
        TextField(
          controller: pin,
          keyboardType: TextInputType.number,
          maxLength: 5,
          obscureText: true,
          decoration: const InputDecoration(labelText: 'New 5-digit PIN'),
        ),
        if (!resetDone && verificationId == null)
          TextButton(
            onPressed: busy ? null : send,
            child: const Text('Send SMS code'),
          ),
        if (!resetDone && verificationId != null) ...[
          TextField(
            controller: sms,
            keyboardType: TextInputType.number,
            maxLength: 6,
            decoration: const InputDecoration(labelText: 'SMS code'),
          ),
          TextButton(
            onPressed: busy
                ? null
                : () {
                    final id = verificationId;
                    if (id != null && sms.text.length == 6) {
                      confirmCredential(
                        PhoneAuthProvider.credential(
                          verificationId: id,
                          smsCode: sms.text,
                        ),
                      );
                    }
                  },
            child: const Text('Verify and reset'),
          ),
        ],
        if (resetDone)
          TextButton(
            onPressed: busy ? null : savePin,
            child: const Text('Set new PIN'),
          ),
        if (busy) const LinearProgressIndicator(minHeight: 2),
        if (error.isNotEmpty)
          Text(error, style: const TextStyle(color: Colors.red)),
      ],
    ),
  );
}
