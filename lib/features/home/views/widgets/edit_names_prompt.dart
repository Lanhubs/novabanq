import 'package:flutter/material.dart';
import 'package:novabanq/core/network/api_client.dart';
import 'package:novabanq/core/network/profile_api.dart';

class EditNamesPrompt extends StatefulWidget {
  const EditNamesPrompt({
    super.key,
    required this.profile,
    required this.onSaved,
  });
  final Map<String, dynamic> profile;
  final VoidCallback onSaved;

  @override
  State<EditNamesPrompt> createState() => _EditNamesPromptState();
}

class _EditNamesPromptState extends State<EditNamesPrompt> {
  late final first = TextEditingController(
    text: widget.profile['first_name']?.toString(),
  );
  late final middle = TextEditingController(
    text: widget.profile['middle_name']?.toString(),
  );
  late final last = TextEditingController(
    text: widget.profile['last_name']?.toString(),
  );
  bool busy = false;
  String error = '';

  @override
  void dispose() {
    first.dispose();
    middle.dispose();
    last.dispose();
    super.dispose();
  }

  Future<void> save() async {
    if (busy) return;
    final names = [first.text.trim(), middle.text.trim(), last.text.trim()];
    if (names.any((name) => name.isEmpty || name.length > 80)) {
      setState(() => error = 'Enter all three legal names.');
      return;
    }
    setState(() {
      busy = true;
      error = '';
    });
    try {
      await ProfileApi(ApiClient()).updateNames(names[0], names[1], names[2]);
      widget.onSaved();
      if (mounted) Navigator.of(context).pop();
    } on ApiFailure catch (failure) {
      if (mounted) setState(() => error = failure.message);
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
        const Text('Legal name', style: TextStyle(fontWeight: FontWeight.bold)),
        TextField(
          controller: first,
          decoration: const InputDecoration(labelText: 'First name'),
        ),
        TextField(
          controller: middle,
          decoration: const InputDecoration(labelText: 'Middle name'),
        ),
        TextField(
          controller: last,
          decoration: const InputDecoration(labelText: 'Last name'),
        ),
        TextButton(
          onPressed: busy ? null : save,
          child: const Text('Save names'),
        ),
        if (busy) const LinearProgressIndicator(minHeight: 2),
        if (error.isNotEmpty)
          Text(error, style: const TextStyle(color: Colors.red)),
      ],
    ),
  );
}
