import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart';

class FirebaseBootstrap {
  static bool ready = false;
  static const apiKey = String.fromEnvironment(
    'FIREBASE_API_KEY',
    defaultValue: 'AIzaSyBn1GE3KqkiP_65RL_GfRA43j6_qJuEYDY',
  );
  static const appId = String.fromEnvironment(
    'FIREBASE_APP_ID',
    defaultValue: '1:794566240712:android:41e95067414f261668b8fd',
  );
  static const projectId = String.fromEnvironment(
    'FIREBASE_PROJECT_ID',
    defaultValue: 'novabanq-ec947',
  );
  static const senderId = String.fromEnvironment(
    'FIREBASE_SENDER_ID',
    defaultValue: '794566240712',
  );
  static const googleClientId = String.fromEnvironment(
    'GOOGLE_CLIENT_ID',
    defaultValue:
        '794566240712-mda8oitbadtul5g09uqgjllb088ddfam.apps.googleusercontent.com',
  );
  static const googleIosClientId = String.fromEnvironment(
    'GOOGLE_IOS_CLIENT_ID',
  );

  static Future<void> initialize() async {
    try {
      if (Firebase.apps.isNotEmpty) {
        ready = true;
        return;
      }
      if ([apiKey, appId, projectId, senderId].any((value) => value.isEmpty)) {
        if (!kIsWeb &&
            (defaultTargetPlatform == TargetPlatform.android ||
                defaultTargetPlatform == TargetPlatform.iOS)) {
          await Firebase.initializeApp();
          ready = true;
          return;
        }
        return;
      }
      await Firebase.initializeApp(
        options: FirebaseOptions(
          apiKey: apiKey,
          appId: appId,
          messagingSenderId: senderId,
          projectId: projectId,
          storageBucket: '$projectId.firebasestorage.app',
          authDomain: kIsWeb ? '$projectId.firebaseapp.com' : null,
        ),
      );
      ready = true;
    } catch (e) {
      debugPrint('Firebase initialization failed: $e');
    }
  }
}
