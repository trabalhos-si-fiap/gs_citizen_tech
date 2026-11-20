// `POST /v1/reports`: sem categoria escolhida, o campo não vai (a IA classifica
// sem palpite); o endereço vai em `address` (aparado, até 200 caracteres).

import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:reclame_ja_mobile/services/api_client.dart';
import 'package:reclame_ja_mobile/services/outbox_store.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Responde ao `POST /v1/reports` e guarda os corpos enviados.
MockClient _api(List<Map<String, dynamic>> sent) => MockClient((request) async {
      sent.add(jsonDecode(request.body) as Map<String, dynamic>);
      return http.Response(
        jsonEncode({
          'id': sent.last['id'],
          'protocol': 'RPT-2026-000001',
          'status': 'recebido',
          'received_at': '2026-11-19T23:18:13Z',
          'triage_state': 'pending_classification',
        }),
        201,
        headers: {'content-type': 'application/json; charset=utf-8'},
      );
    });

Future<Map<String, dynamic>> _create({String? category, String? address}) async {
  final sent = <Map<String, dynamic>>[];
  await http.runWithClient(
    () => ApiClient().createReport(
      id: 'c0ffee00-0000-4000-8000-000000000001',
      description: 'Falta de remédio na UBS',
      lat: -23.55,
      lon: -46.63,
      anonymous: false,
      category: category,
      address: address,
    ),
    () => _api(sent),
  );
  return sent.single;
}

void main() {
  test('without a chosen category the field is not sent', () async {
    final body = await _create();

    expect(body, isNot(contains('category')));
  });

  test('a chosen category is sent', () async {
    final body = await _create(category: 'saude_atendimento');

    expect(body['category'], 'saude_atendimento');
  });

  test('the address is sent trimmed', () async {
    final body = await _create(address: '  Rua Exemplo, 123 – Sé, São Paulo ');

    expect(body['address'], 'Rua Exemplo, 123 – Sé, São Paulo');
  });

  test('a long address is cut to the 200 characters the API accepts',
      () async {
    final body = await _create(address: 'R' * 250);

    expect(body['address'], hasLength(200));
  });

  test('an unknown address is not sent', () async {
    expect(await _create(), isNot(contains('address')));
    expect(await _create(address: '  '), isNot(contains('address')));
  });

  test('a pending report keeps its address and lack of category', () async {
    SharedPreferences.setMockInitialValues({});
    await OutboxStore.enqueue({
      'id': 'c0ffee00-0000-4000-8000-000000000002',
      'description': 'Buraco na calçada',
      'has_photo': false,
      'photo_path': null,
      'lat': -23.55,
      'lon': -46.63,
      'location_accuracy_m': 8.0,
      'anonymous': false,
      'address': 'Rua Exemplo, 123 – Sé, São Paulo',
      'client_created_at': '2026-11-19T23:18:13.000Z',
    });
    final sent = <Map<String, dynamic>>[];

    final result =
        await http.runWithClient(() => ApiClient().flushOutbox(), () => _api(sent));

    expect(result.synced, 1);
    expect(sent.single['address'], 'Rua Exemplo, 123 – Sé, São Paulo');
    expect(sent.single, isNot(contains('category')));
  });
}
