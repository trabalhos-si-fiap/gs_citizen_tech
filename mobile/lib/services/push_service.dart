import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';

import 'api_client.dart';

class PushService {
  PushService._();

  static const _enabled = bool.fromEnvironment(
    'ENABLE_FIREBASE_PUSH',
    defaultValue: false,
  );
  static final _reportUpdates = StreamController<String?>.broadcast();
  static Stream<String?> get reportUpdates => _reportUpdates.stream;
  static StreamSubscription<String>? _tokenSubscription;
  static StreamSubscription<RemoteMessage>? _openedSubscription;
  static StreamSubscription<RemoteMessage>? _foregroundSubscription;

  static Future<void> initializeAfterLogin() async {
    if (!_enabled) return;
    if (Firebase.apps.isEmpty) await Firebase.initializeApp();

    final messaging = FirebaseMessaging.instance;
    final permission = await messaging.requestPermission(
      alert: true,
      badge: true,
      sound: true,
    );
    if (permission.authorizationStatus == AuthorizationStatus.denied) {
      final token = await messaging.getToken();
      if (token != null) await ApiClient().removeDevice(token);
      await messaging.deleteToken();
      await dispose();
      return;
    }

    final token = await messaging.getToken();
    if (token != null) {
      await ApiClient().registerDevice(
        pushToken: token,
        platform: Platform.isAndroid ? 'android' : 'ios',
      );
    }

    await _tokenSubscription?.cancel();
    _tokenSubscription = messaging.onTokenRefresh.listen(
      (newToken) async {
        await ApiClient().registerDevice(
          pushToken: newToken,
          platform: Platform.isAndroid ? 'android' : 'ios',
        );
      },
      onError: (Object error, StackTrace stackTrace) {
        debugPrint('Falha ao sincronizar token de notificações: $error');
      },
    );

    await _openedSubscription?.cancel();
    _openedSubscription = FirebaseMessaging.onMessageOpenedApp.listen(
      (message) => _reportUpdates.add(message.data['report_id']?.toString()),
    );
    await _foregroundSubscription?.cancel();
    _foregroundSubscription = FirebaseMessaging.onMessage.listen(
      (message) => _reportUpdates.add(message.data['report_id']?.toString()),
    );

    final initialMessage = await messaging.getInitialMessage();
    if (initialMessage != null) {
      _reportUpdates.add(initialMessage.data['report_id']?.toString());
    }
  }

  static Future<void> removeCurrentDevice() async {
    if (!_enabled || Firebase.apps.isEmpty) return;
    final token = await FirebaseMessaging.instance.getToken();
    if (token != null) await ApiClient().removeDevice(token);
    await FirebaseMessaging.instance.deleteToken();
  }

  static Future<void> dispose() async {
    await _tokenSubscription?.cancel();
    await _openedSubscription?.cancel();
    await _foregroundSubscription?.cancel();
  }
}
