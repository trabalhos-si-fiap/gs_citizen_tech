import 'package:flutter/widgets.dart' show Locale;
import 'package:geocoding/geocoding.dart';

/// Endereço legível de uma coordenada, para o munícipe não ver latitude e
/// longitude.
abstract class AddressLookup {
  /// Endereço formatado com [formatAddress], ou `null` sem resultado.
  Future<String?> addressFor(double latitude, double longitude);
}

/// Sem geocodificação: as telas mostram as coordenadas.
class NoAddressLookup implements AddressLookup {
  const NoAddressLookup();

  @override
  Future<String?> addressFor(double latitude, double longitude) async => null;
}

/// Geocodificação reversa no aparelho (Geocoder do Android, CLGeocoder do
/// iOS), sem chave de API.
class DeviceAddressLookup implements AddressLookup {
  const DeviceAddressLookup();

  @override
  Future<String?> addressFor(double latitude, double longitude) async {
    final places = await Geocoding(locale: const Locale('pt', 'BR'))
        .placemarkFromCoordinates(latitude, longitude);
    return places.isEmpty ? null : addressFromPlacemark(places.first);
  }
}

/// Geocodificador usado pelo app.
const AddressLookup defaultAddressLookup = DeviceAddressLookup();

/// Endereço de um [Placemark]. Prefere nome da rua + número; no Android
/// `street` às vezes já vem "Rua X, 123" e serve de reserva.
String? addressFromPlacemark(Placemark place) {
  String clean(String? part) {
    final text = part?.trim() ?? '';
    return text == 'Unnamed Road' ? '' : text;
  }

  final thoroughfare = clean(place.thoroughfare);
  final city = clean(place.locality);
  return formatAddress(
    street: thoroughfare.isNotEmpty ? thoroughfare : clean(place.street),
    number: thoroughfare.isNotEmpty ? place.subThoroughfare : null,
    district: place.subLocality,
    city: city.isNotEmpty ? city : place.subAdministrativeArea,
  );
}

/// "Rua Exemplo, 123 – Bairro, Cidade", sem as partes vazias. O número só
/// aparece junto da rua.
String? formatAddress({
  String? street,
  String? number,
  String? district,
  String? city,
}) {
  String join(List<String?> parts, String separator) => parts
      .map((part) => part?.trim() ?? '')
      .where((part) => part.isNotEmpty)
      .join(separator);

  final streetLine =
      (street?.trim() ?? '').isEmpty ? '' : join([street, number], ', ');
  final text = join([streetLine, join([district, city], ', ')], ' – ');
  return text.isEmpty ? null : text;
}

/// Coordenadas como detalhe secundário: "-23.55000, -46.63331".
String formatCoordinates(double latitude, double longitude) =>
    '${latitude.toStringAsFixed(5)}, ${longitude.toStringAsFixed(5)}';
