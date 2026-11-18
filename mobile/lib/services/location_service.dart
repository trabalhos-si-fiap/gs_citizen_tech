import 'package:geolocator/geolocator.dart';

class GeoPoint {
  const GeoPoint(this.latitude, this.longitude);

  final double latitude;
  final double longitude;
}

/// Centro padrão (Praça da Sé, São Paulo) quando a localização não está disponível.
const GeoPoint defaultCenter = GeoPoint(-23.5505, -46.6333);

abstract class LocationService {
  Future<GeoPoint> current();
}

/// Localização do aparelho; sem permissão ou serviço desligado, usa o centro padrão.
class DeviceLocationService implements LocationService {
  const DeviceLocationService();

  @override
  Future<GeoPoint> current() async {
    try {
      if (!await Geolocator.isLocationServiceEnabled()) return defaultCenter;
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.denied ||
          permission == LocationPermission.deniedForever) {
        return defaultCenter;
      }
      final position = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.medium,
          timeLimit: Duration(seconds: 10),
        ),
      );
      return GeoPoint(position.latitude, position.longitude);
    } catch (_) {
      return defaultCenter;
    }
  }
}
