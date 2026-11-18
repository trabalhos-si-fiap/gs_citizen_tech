import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:reclame_ja_mobile/services/outbox_store.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('enqueue replaces duplicate drafts and removes their persisted photo',
      () async {
    final directory = await Directory.systemTemp.createTemp('report-outbox-');
    final photo = File('${directory.path}/report.jpg');
    await photo.writeAsBytes([1, 2, 3]);

    await OutboxStore.enqueue({
      'id': 'draft-id',
      'description': 'Primeira versão',
      'photo_path': photo.path,
    });
    await OutboxStore.enqueue({
      'id': 'draft-id',
      'description': 'Versão atualizada',
      'photo_path': photo.path,
    });

    final drafts = await OutboxStore.load();
    expect(drafts, hasLength(1));
    expect(drafts.single['description'], 'Versão atualizada');

    await OutboxStore.remove('draft-id');
    expect(await OutboxStore.load(), isEmpty);
    expect(await photo.exists(), isFalse);
    await directory.delete();
  });
}
