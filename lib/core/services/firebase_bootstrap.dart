import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart';

class FirebaseBootstrap {
  static bool ready = false;
  static const apiKey = String.fromEnvironment('FIREBASE_API_KEY');
  static const appId = String.fromEnvironment('FIREBASE_APP_ID');
  static const projectId = String.fromEnvironment('FIREBASE_PROJECT_ID');
  static const senderId = String.fromEnvironment('FIREBASE_SENDER_ID');
  static const googleClientId = String.fromEnvironment('GOOGLE_CLIENT_ID');
  static const googleIosClientId = String.fromEnvironment(
    'GOOGLE_IOS_CLIENT_ID',
  );

  static Future<void> initialize() async {
    if ([apiKey, appId, projectId, senderId].any((value) => value.isEmpty)) {
      return;
    }
    await Firebase.initializeApp(
      options: FirebaseOptions(
        apiKey: apiKey,
        appId: appId,
        messagingSenderId: senderId,
        projectId: projectId,
        authDomain: kIsWeb ? '$projectId.firebaseapp.com' : null,
      ),
    );
    ready = true;
  }
}
