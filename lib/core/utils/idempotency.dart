import 'dart:math';

class Idempotency {
  static String generateKey() {
    final random = Random.secure();
    final values = List<int>.generate(16, (i) => random.nextInt(256));
    values[6] = (values[6] & 0x0f) | 0x40; // Version 4
    values[8] = (values[8] & 0x3f) | 0x80; // Variant 10xx
    final hex = [
      for (int i = 0; i < 16; i++)
        values[i].toRadixString(16).padLeft(2, '0')
    ].join();
    return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20, 32)}';
  }
}
