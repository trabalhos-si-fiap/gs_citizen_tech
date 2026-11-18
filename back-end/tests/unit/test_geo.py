import unittest

from app.core.geo import bounding_box, haversine_m


class HaversineTests(unittest.TestCase):
    def test_same_point_has_zero_distance(self) -> None:
        self.assertEqual(haversine_m(-23.55, -46.63, -23.55, -46.63), 0.0)

    def test_one_degree_of_longitude_on_equator(self) -> None:
        self.assertAlmostEqual(haversine_m(0, 0, 0, 1), 111_195, delta=1)

    def test_known_distance_between_se_and_masp(self) -> None:
        # Praça da Sé -> MASP, aproximadamente 2,6 km em linha reta.
        distance = haversine_m(-23.5503, -46.6340, -23.5614, -46.6559)

        self.assertAlmostEqual(distance, 2_560, delta=60)


class BoundingBoxTests(unittest.TestCase):
    def test_box_contains_points_at_radius_in_every_direction(self) -> None:
        lat, lon, radius = -23.55, -46.63, 1_000
        box = bounding_box(lat, lon, radius)

        for bearing_lat, bearing_lon in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            with self.subTest(direction=(bearing_lat, bearing_lon)):
                # Avança em passos pequenos até atingir o raio.
                point_lat, point_lon = lat, lon
                while haversine_m(lat, lon, point_lat, point_lon) < radius:
                    point_lat += bearing_lat * 1e-5
                    point_lon += bearing_lon * 1e-5
                self.assertTrue(box.contains(point_lat - bearing_lat * 1e-5, point_lon - bearing_lon * 1e-5))

    def test_box_is_tight_around_radius(self) -> None:
        box = bounding_box(0, 0, 1_000)

        self.assertAlmostEqual(box.max_lat - box.min_lat, 2 * 1_000 / 111_195, places=4)

    def test_box_is_clamped_to_valid_latitudes(self) -> None:
        box = bounding_box(89.999, 0, 5_000)

        self.assertLessEqual(box.max_lat, 90)
        self.assertEqual((box.min_lon, box.max_lon), (-180, 180))


if __name__ == "__main__":
    unittest.main()
