import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../app_theme.dart';
import '../../services/report_store.dart';
import '../report_detail_screen.dart';
import '../new_report_wizard.dart';
import '../welcome_screen.dart';
import '../emergency_screen.dart';

class MapTab extends StatefulWidget {
  final bool isVisitor;
  final String userName;

  const MapTab({
    super.key,
    required this.isVisitor,
    required this.userName,
  });

  @override
  State<MapTab> createState() => _MapTabState();
}

class _MapTabState extends State<MapTab> {
  String _activeFilter = 'Todos';
  List<Report> _reportsList = [];
  Report? _selectedMapReport;

  @override
  void initState() {
    super.initState();
    _reportsList = ReportStore().allReports;
    _listenToStore();
  }

  void _listenToStore() {
    ReportStore().reportsStream.listen((list) {
      if (mounted) {
        setState(() {
          _reportsList = list;
        });
      }
    });
  }

  List<Report> _getFilteredReports() {
    if (_activeFilter == 'Todos') {
      return _reportsList;
    }
    return _reportsList.where((r) => r.category == _activeFilter).toList();
  }

  int _getCategoryCount(String cat) {
    if (cat == 'Todos') {
      return _reportsList.length;
    }
    return _reportsList.where((r) => r.category == cat).toList().length;
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
            'Para registrar problemas urbanos de zeladoria, por favor crie uma conta ou faça login no Reclame Já.'),
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
          // 1. Vector Map Canvas (Background)
          Container(
            color: const Color(0xFFEAF1F8),
            child: CustomPaint(
              size: Size.infinite,
              painter: MapPainter(),
            ),
          ),

          // Pulsing user location indicator
          const Positioned(
            left: 195,
            top: 265,
            child: _UserLocationPin(),
          ),

          // Interactive Map Pins dynamically loaded from ReportStore!
          _buildMapPins(),

          // 2. Floating Header Box (Top Greeting + Filter Chips)
          SafeArea(
            child: Padding(
              padding:
                  const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Profile Greeting panel
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
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Text(
                                  'Olá, ${widget.userName}',
                                  style: textTheme.headlineSmall?.copyWith(
                                      fontSize: 18,
                                      fontWeight: FontWeight.bold),
                                ),
                                const SizedBox(width: 4),
                                const Text('👋',
                                    style: TextStyle(fontSize: 16)),
                              ],
                            ),
                            const SizedBox(height: 2),
                            Row(
                              children: [
                                Container(
                                  width: 8,
                                  height: 8,
                                  decoration: const BoxDecoration(
                                      color: Colors.green,
                                      shape: BoxShape.circle),
                                ),
                                const SizedBox(width: 6),
                                Text(
                                  'Jardim das Flores, São Paulo',
                                  style: textTheme.bodySmall?.copyWith(
                                      color: ReclameJaColors.textMuted),
                                ),
                              ],
                            ),
                          ],
                        ),
                        // Emergency Shortcut + Notification
                        Row(
                          children: [
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
                            Stack(
                              alignment: Alignment.topRight,
                              children: [
                                Container(
                                  width: 44,
                                  height: 44,
                                  decoration: BoxDecoration(
                                    color: ReclameJaColors.surfaceLow,
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                  child: const Icon(Icons.notifications_none,
                                      color: ReclameJaColors.textDark,
                                      size: 22),
                                ),
                                Container(
                                  margin: const EdgeInsets.only(top: 4),
                                  padding: const EdgeInsets.all(4),
                                  decoration: const BoxDecoration(
                                      color: ReclameJaColors.primaryYellow,
                                      shape: BoxShape.circle),
                                  child: const Text('2',
                                      style: TextStyle(
                                          fontSize: 8,
                                          fontWeight: FontWeight.bold,
                                          color: ReclameJaColors.textDark)),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 10),

                  // Horizontal Category Filter Chips
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

          // 3. Floating lateral controls
          Positioned(
            right: 16,
            bottom: 96,
            child: Column(
              children: [
                _FloatingMapButton(
                  icon: Icons.my_location,
                  onTap: () {
                    setState(() {
                      _selectedMapReport = null;
                    });
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                          content:
                              Text('Centralizado na sua localização atual.')),
                    );
                  },
                ),
                const SizedBox(height: 10),
                _FloatingMapButton(
                  icon: Icons.layers,
                  onTap: () {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                          content:
                              Text('Alternando camadas do OpenStreetMap...')),
                    );
                  },
                ),
              ],
            ),
          ),

          // 4. Pin Preview Overlay Card (when a pin is clicked)
          if (_selectedMapReport != null)
            Positioned(
              left: 16,
              right: 16,
              bottom: 96,
              child: _buildPinPreviewCard(_selectedMapReport!),
            ),

          // 5. Prominent floating "+ Reportar" trigger
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
    final count = _getCategoryCount(label);

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
          const SizedBox(width: 6),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
            decoration: BoxDecoration(
              color: isSelected
                  ? ReclameJaColors.textDark
                  : ReclameJaColors.surfaceDim,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              '$count',
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.bold,
                color: isSelected
                    ? ReclameJaColors.primaryYellow
                    : ReclameJaColors.textDark,
              ),
            ),
          ),
        ],
      ),
      backgroundColor: Colors.white.withValues(alpha: 0.95),
      selectedColor: ReclameJaColors.primaryYellow,
      checkmarkColor: Colors.transparent,
      showCheckmark: false,
      shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: const BorderSide(color: ReclameJaColors.borderSlate)),
      onSelected: (val) {
        setState(() {
          _activeFilter = label;
          _selectedMapReport = null; // Close any pin preview
        });
      },
    );
  }

  Widget _buildMapPins() {
    // We map reports to coordinates on the custom painter
    // #CV-2023-8941 -> x: 125, y: 195 (Poda / Pavimentação)
    // #CV-2023-5510 -> x: 295, y: 210 (Ônibus)
    // #CV-2023-1122 -> x: 80, y: 340 (Praça / Luz)

    final filtered = _getFilteredReports();

    return Stack(
      children: filtered.map((r) {
        double left = 100;
        double top = 100;
        Color color = ReclameJaColors.tertiaryBlue;
        IconData icon = Icons.warning;

        if (r.id.contains('8941')) {
          left = 125;
          top = 195;
          color =
              r.status == 'Resolvido' ? Colors.green : Colors.amber.shade600;
          icon = Icons.park;
        } else if (r.id.contains('5510')) {
          left = 295;
          top = 210;
          color = r.status == 'Resolvido'
              ? Colors.green
              : ReclameJaColors.textMuted;
          icon = Icons.directions_bus;
        } else if (r.id.contains('1122')) {
          left = 80;
          top = 340;
          color = Colors.green;
          icon = Icons.check;
        } else {
          // Dynamic pins for reports entered during current session
          left = 280;
          top = 95;
          color = ReclameJaColors.alertRed;
          icon = Icons.warning;
        }

        return Positioned(
          left: left - 16,
          top: top - 40,
          child: GestureDetector(
            onTap: () {
              setState(() {
                _selectedMapReport = r;
              });
            },
            child: Column(
              children: [
                // mini label
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(6),
                    boxShadow: const [
                      BoxShadow(color: Colors.black12, blurRadius: 3)
                    ],
                  ),
                  child: Text(
                    r.subcategory.split(' ').first,
                    style: const TextStyle(
                        fontSize: 9,
                        fontWeight: FontWeight.bold,
                        color: ReclameJaColors.textDark),
                  ),
                ),
                const SizedBox(height: 2),
                Container(
                  width: 32,
                  height: 32,
                  decoration: BoxDecoration(
                    color: color,
                    shape: BoxShape.circle,
                    border: Border.all(color: Colors.white, width: 2),
                    boxShadow: const [
                      BoxShadow(
                          color: Colors.black26,
                          blurRadius: 4,
                          offset: Offset(0, 2))
                    ],
                  ),
                  child: Icon(icon, color: Colors.white, size: 16),
                ),
                Container(
                  width: 6,
                  height: 6,
                  decoration: BoxDecoration(
                    color: color,
                    borderRadius:
                        const BorderRadius.vertical(bottom: Radius.circular(9)),
                  ),
                ),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildPinPreviewCard(Report report) {
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
                        report.title,
                        style: textTheme.titleMedium
                            ?.copyWith(fontWeight: FontWeight.bold),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 2),
                      Text(
                        report.location,
                        style: textTheme.bodySmall
                            ?.copyWith(color: ReclameJaColors.textMuted),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close, size: 18),
                  onPressed: () {
                    setState(() {
                      _selectedMapReport = null;
                    });
                  },
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
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                          builder: (context) =>
                              ReportDetailScreen(report: report)),
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

class MapPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    // Draw basic mock roads and street naming grids for visual feedback matching telas/Inicio.html
    final paintRoad = Paint()
      ..color = Colors.white
      ..strokeWidth = 16
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    final paintBlock = Paint()
      ..color = const Color(0xFFDDE8F3)
      ..style = PaintingStyle.fill;

    final paintPark = Paint()
      ..color = const Color(0xFFC8E6D3)
      ..style = PaintingStyle.fill;

    // Draw blocks
    canvas.drawRect(const Rect.fromLTWH(-20, 40, 150, 110), paintBlock);
    canvas.drawRect(const Rect.fromLTWH(150, 20, 130, 100), paintBlock);
    canvas.drawRect(const Rect.fromLTWH(300, -10, 120, 120), paintBlock);
    canvas.drawRect(const Rect.fromLTWH(-10, 180, 120, 140), paintBlock);
    canvas.drawRect(const Rect.fromLTWH(140, 160, 120, 130), paintBlock);
    canvas.drawRect(const Rect.fromLTWH(290, 140, 120, 130), paintBlock);
    canvas.drawRect(const Rect.fromLTWH(-15, 350, 135, 140), paintBlock);
    canvas.drawRect(const Rect.fromLTWH(150, 330, 120, 150), paintBlock);
    canvas.drawRect(const Rect.fromLTWH(300, 300, 120, 160), paintBlock);

    // Draw Praça da Matriz
    final pathPark = Path()
      ..moveTo(150, 160)
      ..quadraticBezierTo(240, 150, 255, 190)
      ..quadraticBezierTo(240, 280, 210, 285)
      ..quadraticBezierTo(145, 250, 150, 160)
      ..close();
    canvas.drawPath(pathPark, paintPark);

    // Draw secondary roads
    canvas.drawLine(const Offset(-20, 160), const Offset(420, 160), paintRoad);
    canvas.drawLine(const Offset(-20, 330), const Offset(420, 330), paintRoad);

    paintRoad.strokeWidth = 18;
    canvas.drawLine(const Offset(130, -20), const Offset(130, 540), paintRoad);

    paintRoad.strokeWidth = 15;
    canvas.drawLine(const Offset(280, -20), const Offset(280, 540), paintRoad);

    // Main Avenue
    paintRoad.color = Colors.white;
    paintRoad.strokeWidth = 26;
    canvas.drawLine(const Offset(40, -30), const Offset(360, 550), paintRoad);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
