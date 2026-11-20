// O munícipe vê endereço, não latitude/longitude: "Rua Exemplo, 123 – Bairro,
// Cidade", sem as partes que o geocodificador não devolveu.

import 'package:flutter_test/flutter_test.dart';
import 'package:reclame_ja_mobile/services/address_service.dart';

void main() {
  test('formats street, number, district and city', () {
    expect(
      formatAddress(
        street: 'Rua Exemplo',
        number: '123',
        district: 'Bela Vista',
        city: 'São Paulo',
      ),
      'Rua Exemplo, 123 – Bela Vista, São Paulo',
    );
  });

  test('skips the parts the geocoder did not return', () {
    expect(formatAddress(street: 'Rua Exemplo', city: 'São Paulo'),
        'Rua Exemplo – São Paulo');
    expect(formatAddress(street: ' ', district: 'Sé', city: 'São Paulo'),
        'Sé, São Paulo');
    expect(formatAddress(number: '123', city: 'São Paulo'), 'São Paulo');
  });

  test('nothing useful means no address', () {
    expect(formatAddress(), isNull);
    expect(formatAddress(street: '', number: '', district: ' '), isNull);
  });

  test('coordinates are the secondary detail', () {
    expect(formatCoordinates(-23.550001, -46.633309), '-23.55000, -46.63331');
  });
}
