import 'dart:convert';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class TransferAttemptStore {
  static const _storage = FlutterSecureStorage();

  static String? _storageKey(String fingerprint) {
    final uid = FirebaseAuth.instance.currentUser?.uid;
    final suffix = base64Url.encode(utf8.encode(fingerprint));
    return uid == null ? null : 'transfer_attempt_${uid}_$suffix';
  }

  static Future<String?> read(String fingerprint) async {
    final key = _storageKey(fingerprint);
    if (key == null) return null;
    final raw = await _storage.read(key: key);
    if (raw == null) return null;
    final data = jsonDecode(raw);
    return data is Map && data['fingerprint'] == fingerprint
        ? data['idempotency_key']?.toString()
        : null;
  }

  static Future<void> write(String fingerprint, String idempotencyKey) async {
    final key = _storageKey(fingerprint);
    if (key == null) return;
    await _storage.write(
      key: key,
      value: jsonEncode({
        'fingerprint': fingerprint,
        'idempotency_key': idempotencyKey,
      }),
    );
  }

  static Future<void> clear(String fingerprint) async {
    final key = _storageKey(fingerprint);
    if (key != null) await _storage.delete(key: key);
  }
}
