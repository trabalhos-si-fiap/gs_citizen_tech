"""Cálculos geográficos simples (esfera média da Terra), sem dependências externas."""

import math
from dataclasses import dataclass

EARTH_RADIUS_M = 6_371_008.8


@dataclass(frozen=True)
class GeoBox:
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float

    def contains(self, latitude: float, longitude: float) -> bool:
        return (
            self.min_lat <= latitude <= self.max_lat
            and self.min_lon <= longitude <= self.max_lon
        )


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância em metros entre dois pontos (fórmula de haversine)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def bounding_box(latitude: float, longitude: float, radius_m: float) -> GeoBox:
    """Retângulo que contém o círculo de raio `radius_m`; usado como pré-filtro no banco.

    Perto dos polos (ou se o círculo cruza o antimeridiano) a longitude não é
    restringida, o que só deixa o pré-filtro mais largo, nunca incorreto.
    """
    delta_lat = math.degrees(radius_m / EARTH_RADIUS_M)
    min_lat = max(latitude - delta_lat, -90.0)
    max_lat = min(latitude + delta_lat, 90.0)

    # A maior largura em longitude ocorre na borda mais próxima do polo.
    cos_lat = math.cos(math.radians(max(abs(min_lat), abs(max_lat))))
    if cos_lat < 1e-6:
        return GeoBox(min_lat, max_lat, -180, 180)
    delta_lon = math.degrees(radius_m / (EARTH_RADIUS_M * cos_lat))
    min_lon, max_lon = longitude - delta_lon, longitude + delta_lon
    if min_lon < -180 or max_lon > 180 or max_lat >= 90 or min_lat <= -90:
        return GeoBox(min_lat, max_lat, -180, 180)
    return GeoBox(min_lat, max_lat, min_lon, max_lon)
