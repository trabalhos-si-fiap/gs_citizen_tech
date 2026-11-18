import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../app_theme.dart';
import 'welcome_screen.dart';
import 'tabs/map_tab.dart';
import 'tabs/feed_tab.dart';
import 'tabs/reports_tab.dart';
import 'tabs/region_tab.dart';
import 'tabs/profile_tab.dart';
import 'new_report_wizard.dart';

class HomeShell extends StatefulWidget {
  final bool isVisitor;
  final String userName;

  const HomeShell({
    super.key,
    required this.isVisitor,
    required this.userName,
  });

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _currentIndex = 0;

  late final List<Widget> _tabs;

  @override
  void initState() {
    super.initState();
    _tabs = [
      MapTab(isVisitor: widget.isVisitor, userName: widget.userName),
      ReportsTab(isVisitor: widget.isVisitor),
      FeedTab(isVisitor: widget.isVisitor, userName: widget.userName),
      RegionTab(isVisitor: widget.isVisitor),
      ProfileTab(isVisitor: widget.isVisitor, userName: widget.userName),
    ];
  }

  void _onTabTapped(int index) {
    setState(() {
      _currentIndex = index;
    });
  }

  void _handleNewReportAction() {
    if (widget.isVisitor) {
      _showLoginRequiredDialog();
    } else {
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (context) => const NewReportWizard(),
        ),
      );
    }
  }

  void _showLoginRequiredDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(
          'Login Necessário',
          style: GoogleFonts.spaceGrotesk(
            fontWeight: FontWeight.bold,
            color: ReclameJaColors.textDark,
          ),
        ),
        content: Text(
          'Como visitante, você pode explorar e acompanhar as ocorrências do bairro. Para registrar um novo problema, por favor crie uma conta ou faça login.',
          style: GoogleFonts.hankenGrotesk(),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(
              'Continuar explorando',
              style: GoogleFonts.hankenGrotesk(
                color: ReclameJaColors.textMuted,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: ReclameJaColors.primaryYellow,
              foregroundColor: ReclameJaColors.textDark,
              minimumSize: const Size(120, 44),
            ),
            onPressed: () {
              Navigator.pop(context); // Close dialog
              Navigator.pushReplacement(
                context,
                MaterialPageRoute(builder: (context) => const WelcomeScreen()),
              );
            },
            child: const Text('Fazer Login'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: ReclameJaColors.surfaceMain,
      body: IndexedStack(
        index: _currentIndex,
        children: _tabs,
      ),
      // Float Action Button centrally aligned as in the mockups
      floatingActionButton: _currentIndex == 0
          ? null // Managed inside MapTab's stack for strict HTML mockup layout fidelity
          : FloatingActionButton.extended(
              onPressed: _handleNewReportAction,
              icon: const Icon(Icons.add_a_photo_outlined),
              label: const Text(
                'Reportar problema',
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
            ),
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.06),
              blurRadius: 10,
              offset: const Offset(0, -2),
            ),
          ],
        ),
        child: NavigationBar(
          selectedIndex: _currentIndex,
          onDestinationSelected: _onTabTapped,
          backgroundColor: ReclameJaColors.surfaceBright,
          indicatorColor: ReclameJaColors.primaryYellow,
          destinations: const [
            NavigationDestination(
              icon: Icon(Icons.map_outlined),
              selectedIcon: Icon(Icons.map, color: ReclameJaColors.textDark),
              label: 'Mapa',
            ),
            NavigationDestination(
              icon: Icon(Icons.assignment_outlined),
              selectedIcon:
                  Icon(Icons.assignment, color: ReclameJaColors.textDark),
              label: 'Reportes',
            ),
            NavigationDestination(
              icon: Icon(Icons.dynamic_feed_outlined),
              selectedIcon:
                  Icon(Icons.dynamic_feed, color: ReclameJaColors.textDark),
              label: 'Feed',
            ),
            NavigationDestination(
              icon: Icon(Icons.analytics_outlined),
              selectedIcon:
                  Icon(Icons.analytics, color: ReclameJaColors.textDark),
              label: 'Região',
            ),
            NavigationDestination(
              icon: Icon(Icons.account_circle_outlined),
              selectedIcon:
                  Icon(Icons.account_circle, color: ReclameJaColors.textDark),
              label: 'Perfil',
            ),
          ],
        ),
      ),
    );
  }
}
