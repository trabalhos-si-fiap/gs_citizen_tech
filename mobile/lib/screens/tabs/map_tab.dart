import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:latlong2/latlong.dart';

import '../../app_theme.dart';
import '../../services/location_service.dart';
import '../../services/nearby_service.dart';
import '../emergency_screen.dart';
import '../new_report_wizard.dart';
import '../report_detail_screen.dart';
import '../welcome_screen.dart';
import 'feed_tab.dart' show categoryIcon;

/// Raio consultado ao redor do centro do mapa, em metros.
const int mapRadiusM = 2000;

/// Tiles públicos do OpenStreetMap: a política de uso deles não cobre tráfego
/// de produção; em produção, trocar por provedor próprio ou contratado.
const String osmTileUrl = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

class MapTab extends StatefulWidget {
  final bool isVisitor;
  final String userName;
  final NearbyStore? nearbyStore;
  final LocationService? locationService;

  /// Desligado nos testes de widget, que não têm rede.
  final bool showTiles;

  const MapTab({
    super.key,
    required this.isVisitor,
    required this.userName,
    this.nearbyStore,
    this.locationService,
    this.showTiles = true,
  });

  @override
  State<MapTab> createState() => _MapTabState();
}

class _MapTabState extends State<MapTab> {
  String _activeFilter = 'Todos';
  NearbyReport? _selected;
  GeoPoint _userPosition = defaultCenter;
  LatLng _center = LatLng(defaultCenter.latitude, defaultCenter.longitude);
  Timer? _debounce;
  final MapController _mapController = MapController();

  late final NearbyStore _store = widget.nearbyStore ?? NearbyStore.forMap;
  late final LocationService _location =
      widget.locationService ?? const DeviceLocationService();

  @override
  void initState() {
    super.initState();
    _store.addListener(_onStoreChanged);
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _store.removeListener(_onStoreChanged);
    super.dispose();
  }

  void _onStoreChanged() {
    if (mounted) setState(() {});
  }

  Future<void> _locateAndLoad({bool moveCamera = false}) async {
    final position = await _location.current();
    if (!mounted) return;
    setState(() {
      _userPosition = position;
      _center = LatLng(position.latitude, position.longitude);
    });
    if (moveCamera) _mapController.move(_center, 15);
    await _load();
  }

  Future<void> _load() => _store.load(
        latitude: _center.latitude,
        longitude: _center.longitude,
        radiusM: mapRadiusM,
        category: categoryForLabel(_activeFilter),
      );

  void _onMapEvent(MapEvent event) {
    if (event is! MapEventMoveEnd &&
        event is! MapEventFlingAnimationEnd &&
        event is! MapEventDoubleTapZoomEnd &&
        event is! MapEventScrollWheelZoom) {
      return;
    }
    _center = event.camera.center;
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 500), _load);
  }

  void _handleNewReport() {
    if (widget.isVisitor) {
      _showLoginPrompt();
    } else {
      Navigator.push(
        context,
        MaterialPageRoute(builder: (context) => const NewReportWizard()),
      );
    }
  }

  void _showLoginPrompt() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Acesso Restrito',
            style: GoogleFonts.spaceGrotesk(fontWeight: FontWeight.bold)),
        content: const Text(
            'Para registrar problemas ou ver detalhes, por favor crie uma conta ou faça login no Reclame Já.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Continuar explorando',
                style: TextStyle(color: ReclameJaColors.textMuted)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: ReclameJaColors.primaryYellow,
              foregroundColor: ReclameJaColors.textDark,
            ),
            onPressed: () {
              Navigator.pop(context);
              Navigator.pushReplacement(
                context,
                MaterialPageRoute(builder: (context) => const WelcomeScreen()),
              );
            },
            child: const Text('Entrar'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      body: Stack(
        children: [
          FlutterMap(
            mapController: _mapController,
            options: MapOptions(
              initialCenter: _center,
              initialZoom: 15,
              minZoom: 11,
              maxZoom: 19,
              backgroundColor: const Color(0xFFEAF1F8),
              onMapEvent: _onMapEvent,
              // A câmera nasce no centro padrão; ao obter a localização do
              // aparelho, ela é movida para lá antes da primeira consulta.
              onMapReady: () => _locateAndLoad(moveCamera: true),
              onTap: (_, __) => setState(() => _selected = null),
            ),
            children: [
              if (widget.showTiles)
                TileLayer(
                  urlTemplate: osmTileUrl,
                  userAgentPackageName: 'br.fiap.reclameja.mobile',
                ),
              MarkerLayer(markers: [
                Marker(
                  point: LatLng(
                      _userPosition.latitude, _userPosition.longitude),
                  width: 48,
                  height: 48,
                  child: const _UserLocationPin(),
                ),
                ..._store.items.map(_buildMarker),
              ]),
              if (widget.showTiles)
                const SimpleAttributionWidget(
                  source: Text('OpenStreetMap contributors'),
                  alignment: Alignment.bottomLeft,
                ),
            ],
          ),
          SafeArea(
            child: Padding(
              padding:
                  const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.95),
                      borderRadius: BorderRadius.circular(16),
                      boxShadow: const [
                        BoxShadow(
                            color: Colors.black12,
                            blurRadius: 8,
                            offset: Offset(0, 3)),
                      ],
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Olá, ${widget.userName} 👋',
                                style: textTheme.headlineSmall?.copyWith(
                                    fontSize: 18,
                                    fontWeight: FontWeight.bold),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                _store.isLoading
                                    ? 'Buscando ocorrências...'
                                    : _store.error != null
                                        ? 'Sem conexão com o servidor'
                                        : '${_store.items.length} ocorrências num raio de 2 km',
                                style: textTheme.bodySmall?.copyWith(
                                    color: ReclameJaColors.textMuted),
                              ),
                            ],
                          ),
                        ),
                        IconButton(
                          icon: const Icon(Icons.emergency,
                              color: ReclameJaColors.alertRed),
                          tooltip: 'Canais de Emergência',
                          onPressed: () {
                            Navigator.push(
                              context,
                              MaterialPageRoute(
                                  builder: (context) =>
                                      const EmergencyScreen()),
                            );
                          },
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 10),
                  SizedBox(
                    height: 40,
                    child: ListView(
                      scrollDirection: Axis.horizontal,
                      children: [
                        _buildFilterChip('Todos', Icons.all_inclusive),
                        const SizedBox(width: 8),
                        _buildFilterChip('Risco Urbano', Icons.warning,
                            color: Colors.amber.shade700),
                        const SizedBox(width: 8),
                        _buildFilterChip('Transporte', Icons.directions_bus,
                            color: ReclameJaColors.tertiaryBlue),
                        const SizedBox(width: 8),
                        _buildFilterChip('Saúde', Icons.local_hospital,
                            color: ReclameJaColors.alertRed),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          Positioned(
            right: 16,
            bottom: 96,
            child: _FloatingMapButton(
              icon: Icons.my_location,
              onTap: () {
                setState(() => _selected = null);
                _locateAndLoad(moveCamera: true);
              },
            ),
          ),
          if (_selected != null)
            Positioned(
              left: 16,
              right: 16,
              bottom: 96,
              child: _buildPinPreviewCard(_selected!),
            ),
          Positioned(
            bottom: 24,
            left: 24,
            right: 24,
            child: SizedBox(
              height: 54,
              child: ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: ReclameJaColors.primaryYellow,
                  foregroundColor: ReclameJaColors.textDark,
                  elevation: 6,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(28),
                    side: const BorderSide(color: Colors.white, width: 2),
                  ),
                ),
                onPressed: _handleNewReport,
                icon: const Icon(Icons.add_a_photo, size: 24),
                label: const Text(
                  'Reportar problema',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterChip(String label, IconData icon, {Color? color}) {
    final isSelected = _activeFilter == label;
    return FilterChip(
      selected: isSelected,
      label: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != Icons.all_inclusive) ...[
            Icon(icon,
                size: 14,
                color: isSelected
                    ? ReclameJaColors.textDark
                    : (color ?? ReclameJaColors.textMuted)),
            const SizedBox(width: 4),
          ],
          Text(label,
              style:
                  const TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
        ],
      ),
      backgroundColor: Colors.white.withValues(alpha: 0.95),
      selectedColor: ReclameJaColors.primaryYellow,
      showCheckmark: false,
      shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: const BorderSide(color: ReclameJaColors.borderSlate)),
      onSelected: (_) {
        setState(() {
          _activeFilter = label;
          _selected = null;
        });
        _load();
      },
    );
  }

  Color _statusColor(NearbyReport report) => switch (report.status) {
        'resolvido' => Colors.green,
        'em_andamento' => Colors.amber.shade700,
        _ => ReclameJaColors.alertRed,
      };

  Marker _buildMarker(NearbyReport report) {
    final color = _statusColor(report);
    return Marker(
      point: LatLng(report.latitude, report.longitude),
      width: 36,
      height: 36,
      child: GestureDetector(
        key: ValueKey('nearby-marker-${report.id}'),
        onTap: () => setState(() => _selected = report),
        child: Container(
          decoration: BoxDecoration(
            color: color,
            shape: BoxShape.circle,
            border: Border.all(color: Colors.white, width: 2),
            boxShadow: const [
              BoxShadow(
                  color: Colors.black26, blurRadius: 4, offset: Offset(0, 2))
            ],
          ),
          child: Icon(categoryIcon(report.category),
              color: Colors.white, size: 16),
        ),
      ),
    );
  }

  Widget _buildPinPreviewCard(NearbyReport report) {
    final textTheme = Theme.of(context).textTheme;
    return Card(
      elevation: 6,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(12.0),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${report.categoryLabel} • ${report.statusLabel}',
                        style: textTheme.titleMedium
                            ?.copyWith(fontWeight: FontWeight.bold),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 2),
                      Text(
                        '${report.distanceLabel} do centro do mapa',
                        style: textTheme.bodySmall
                            ?.copyWith(color: ReclameJaColors.textMuted),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close, size: 18),
                  onPressed: () => setState(() => _selected = null),
                ),
              ],
            ),
            const Divider(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    const Icon(Icons.thumb_up_alt_outlined,
                        size: 14, color: ReclameJaColors.secondaryEmerald),
                    const SizedBox(width: 4),
                    Text(
                      '${report.confirmationCount} apoios',
                      style: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          color: ReclameJaColors.secondaryEmerald),
                    ),
                  ],
                ),
                TextButton(
                  style: TextButton.styleFrom(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                    minimumSize: Size.zero,
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                  onPressed: () {
                    if (widget.isVisitor) {
                      _showLoginPrompt();
                      return;
                    }
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                          builder: (context) =>
                              ReportDetailScreen(report: report.toReport())),
                    );
                  },
                  child: const Row(
                    children: [
                      Text('Ver detalhes',
                          style: TextStyle(
                              fontWeight: FontWeight.bold,
                              color: ReclameJaColors.secondaryEmerald)),
                      Icon(Icons.arrow_forward,
                          size: 14, color: ReclameJaColors.secondaryEmerald),
                    ],
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _UserLocationPin extends StatelessWidget {
  const _UserLocationPin();

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 48,
      height: 48,
      child: Stack(
        alignment: Alignment.center,
        children: [
          Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(
              color: Colors.green.withValues(alpha: 0.2),
              shape: BoxShape.circle,
            ),
          ),
          Container(
            width: 14,
            height: 14,
            decoration: BoxDecoration(
              color: Colors.white,
              shape: BoxShape.circle,
              boxShadow: const [
                BoxShadow(color: Colors.black26, blurRadius: 4)
              ],
              border: Border.all(color: const Color(0xFF10B981), width: 4),
            ),
          ),
        ],
      ),
    );
  }
}

class _FloatingMapButton extends StatelessWidget {
  final IconData icon;
  final VoidCallback onTap;

  const _FloatingMapButton({required this.icon, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 48,
      height: 48,
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.95),
        borderRadius: BorderRadius.circular(16),
        boxShadow: const [
          BoxShadow(color: Colors.black12, blurRadius: 6, offset: Offset(0, 2))
        ],
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Icon(icon, color: ReclameJaColors.textDark, size: 22),
      ),
    );
  }
}
