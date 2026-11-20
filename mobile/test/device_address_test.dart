// Endereço vindo do geocodificador nativo (pacote `geocoding`): as partes do
// Placemark viram "Rua Exemplo, 123 – Bairro, Cidade".

import 'package:flutter_test/flutter_test.dart';
import 'package:geocoding/geocoding.dart';
import 'package:reclame_ja_mobile/services/address_service.dart';

void main() {
  test('uses the street name and number reported by the geocoder', () {
    expect(
      addressFromPlacemark(const Placemark(
        street: 'Rua Exemplo, 123',
        thoroughfare: 'Rua Exemplo',
        subThoroughfare: '123',
        subLocality: 'Bela Vista',
        locality: 'São Paulo',
      )),
      'Rua Exemplo, 123 – Bela Vista, São Paulo',
    );
  });

  test('falls back to the full street line when there is no street name', () {
    expect(
      addressFromPlacemark(const Placemark(
        street: 'Avenida Central, 45',
        subLocality: 'Centro',
        locality: 'Niterói',
      )),
      'Avenida Central, 45 – Centro, Niterói',
    );
  });

  test('"Unnamed Road" is not shown as a street', () {
    expect(
      addressFromPlacemark(const Placemark(
        street: 'Unnamed Road',
        thoroughfare: 'Unnamed Road',
        subLocality: 'Zona Rural',
        locality: 'Maricá',
      )),
      'Zona Rural, Maricá',
    );
  });

  test('uses the municipality when the city name is missing', () {
    expect(
      addressFromPlacemark(const Placemark(
        thoroughfare: 'Rua Exemplo',
        subThoroughfare: '10',
        subAdministrativeArea: 'Rio de Janeiro',
      )),
      'Rua Exemplo, 10 – Rio de Janeiro',
    );
  });

  test('the app looks addresses up on the device', () {
    expect(defaultAddressLookup, isA<DeviceAddressLookup>());
  });
}
