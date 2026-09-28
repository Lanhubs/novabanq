import 'package:shared_preferences/shared_preferences.dart';

class StorageService {
  static const String _isFirstTimeUserKey = 'isFirstTimeUser';

  /// Sets whether the user is a first-time user (default is true if not specified).
  static Future<bool> setIsFirstTimeUser([bool value = true]) async {
    final prefs = await SharedPreferences.getInstance();
    return await prefs.setBool(_isFirstTimeUserKey, value);
  }

  /// Gets the first-time status. Returns `true` if the key doesn't exist yet.
  static Future<bool> getIsFirstTimeUser() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_isFirstTimeUserKey) ?? true;
  }

  /// Generic getter for String values.
  static Future<String?> get(String key) async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(key);
  }

  /// Generic setter for String values.
  static Future<bool> set(String key, String value) async {
    final prefs = await SharedPreferences.getInstance();
    return await prefs.setString(key, value);
  }

  /// Removes a specific key.
  static Future<bool> remove(String key) async {
    final prefs = await SharedPreferences.getInstance();
    return await prefs.remove(key);
  }

  /// Clears all stored keys.
  static Future<bool> clear() async {
    final prefs = await SharedPreferences.getInstance();
    return await prefs.clear();
  }
}