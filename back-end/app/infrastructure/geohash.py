"""Geração de geohash para indexação geográfica."""

GEOHASH_ALPHABET = "0123456789bcdefghjkmnpqrstuvwxyz"


def encode_geohash(latitude: float, longitude: float, precision: int = 9) -> str:
    lat_range = [-90.0, 90.0]
    lon_range = [-180.0, 180.0]
    bits = (16, 8, 4, 2, 1)
    encoded: list[str] = []
    bit_index = 0
    character = 0
    use_longitude = True

    while len(encoded) < precision:
        coordinate_range = lon_range if use_longitude else lat_range
        coordinate = longitude if use_longitude else latitude
        midpoint = (coordinate_range[0] + coordinate_range[1]) / 2
        if coordinate >= midpoint:
            character |= bits[bit_index]
            coordinate_range[0] = midpoint
        else:
            coordinate_range[1] = midpoint

        use_longitude = not use_longitude
        if bit_index < 4:
            bit_index += 1
        else:
            encoded.append(GEOHASH_ALPHABET[character])
            bit_index = 0
            character = 0

    return "".join(encoded)
