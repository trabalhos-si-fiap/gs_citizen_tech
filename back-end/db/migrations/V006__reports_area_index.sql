-- Pré-filtro retangular de GET /v1/reports/nearby (lat/lon BETWEEN).
-- A distância exata (haversine) é calculada na aplicação sobre os candidatos.
CREATE INDEX ix_reports_lat_lon ON reports (lat, lon, received_at);
