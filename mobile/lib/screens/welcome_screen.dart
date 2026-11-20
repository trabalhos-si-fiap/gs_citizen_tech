import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../app_theme.dart';
import '../services/api_client.dart';
import '../services/push_service.dart';
import '../services/session_store.dart';
import 'home_shell.dart';

class WelcomeScreen extends StatefulWidget {
  const WelcomeScreen({super.key});

  @override
  State<WelcomeScreen> createState() => _WelcomeScreenState();
}

class _WelcomeScreenState extends State<WelcomeScreen> {
  bool _acceptedTerms = false;
  bool _confirmedAge = false;
  final _emailController = TextEditingController();
  final _otpController = TextEditingController();

  final List<Map<String, dynamic>> _benefits = [
    {
      'icon': Icons.photo_camera,
      'title': 'Reporte em segundos',
      'desc':
          'Tire uma foto, marque no mapa e envie sem complicação nem filas burocráticas.',
      'bg': const Color(0xFFE6F7EC),
      'fg': const Color(0xFF006D30),
    },
    {
      'icon': Icons.timeline,
      'title': 'Acompanhe cada passo',
      'desc':
          'Notificações em tempo real com protocolo oficial e encaminhamento direto.',
      'bg': const Color(0xFFFEF9C5),
      'fg': const Color(0xFF656100),
    },
    {
      'icon': Icons.people_outline,
      'title': 'Unidos pelo bairro',
      'desc':
          'Confirme ocorrências de vizinhos para alertar a prefeitura sobre urgências.',
      'bg': const Color(0xFFD1FAE5),
      'fg': const Color(0xFF006D30),
    }
  ];

  @override
  void dispose() {
    _emailController.dispose();
    _otpController.dispose();
    super.dispose();
  }

  void _showEmailLoginSheet() {
    if (!_acceptedTerms || !_confirmedAge) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
              'Por favor, aceite os termos e confirme sua idade antes de continuar.'),
          backgroundColor: ReclameJaColors.alertRed,
        ),
      );
      return;
    }

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: ReclameJaColors.surfaceBright,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (context) {
        return Padding(
          padding: EdgeInsets.only(
            bottom: MediaQuery.of(context).viewInsets.bottom + 24,
            left: 20,
            right: 20,
            top: 24,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Center(
                child: Container(
                  width: 48,
                  height: 5,
                  decoration: BoxDecoration(
                    color: ReclameJaColors.surfaceDim,
                    borderRadius: BorderRadius.circular(999),
                  ),
                ),
              ),
              const SizedBox(height: 20),
              Text(
                'Entrar com e-mail',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 8),
              Text(
                'Enviaremos um código de verificação (OTP) de 6 dígitos para o seu e-mail.',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: ReclameJaColors.textMuted,
                    ),
              ),
              const SizedBox(height: 20),
              TextField(
                controller: _emailController,
                keyboardType: TextInputType.emailAddress,
                decoration: const InputDecoration(
                  hintText: 'exemplo@email.com',
                  prefixIcon: Icon(Icons.email_outlined),
                ),
              ),
              const SizedBox(height: 20),
              ElevatedButton(
                onPressed: () async {
                  final email = _emailController.text.trim();
                  if (email.isEmpty || !email.contains('@')) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text('Digite um e-mail válido.'),
                        backgroundColor: ReclameJaColors.alertRed,
                      ),
                    );
                    return;
                  }
                  try {
                    await ApiClient().requestOtp(
                      email: email,
                      consentVersion: 'v1.0.2',
                    );
                    if (!context.mounted) return;
                    Navigator.pop(context);
                    _showOtpVerificationSheet(email);
                  } catch (error) {
                    if (!context.mounted) return;
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(error.toString()),
                        backgroundColor: ReclameJaColors.alertRed,
                      ),
                    );
                  }
                },
                child: const Text('Enviar código'),
              ),
            ],
          ),
        );
      },
    );
  }

  void _showOtpVerificationSheet(String email) {
    final parentNavigator = Navigator.of(context);
    final parentMessenger = ScaffoldMessenger.of(context);
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: ReclameJaColors.surfaceBright,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (context) {
        return Padding(
          padding: EdgeInsets.only(
            bottom: MediaQuery.of(context).viewInsets.bottom + 24,
            left: 20,
            right: 20,
            top: 24,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Center(
                child: Container(
                  width: 48,
                  height: 5,
                  decoration: BoxDecoration(
                    color: ReclameJaColors.surfaceDim,
                    borderRadius: BorderRadius.circular(999),
                  ),
                ),
              ),
              const SizedBox(height: 20),
              Text(
                'Digite o código',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 8),
              Text(
                'Enviamos um código de 6 dígitos para o e-mail $email. O código expira em 10 minutos.',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: ReclameJaColors.textMuted,
                    ),
              ),
              const SizedBox(height: 20),
              TextField(
                controller: _otpController,
                keyboardType: TextInputType.number,
                maxLength: 6,
                style: GoogleFonts.jetBrainsMono(
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 8,
                ),
                textAlign: TextAlign.center,
                decoration: const InputDecoration(
                  hintText: '123456',
                  counterText: '',
                  prefixIcon: Icon(Icons.lock_outline),
                ),
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: () async {
                  final otp = _otpController.text.trim();
                  if (otp.length != 6) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content:
                            Text('Por favor, digite o código de 6 dígitos.'),
                        backgroundColor: ReclameJaColors.alertRed,
                      ),
                    );
                    return;
                  }

                  try {
                    final data = await ApiClient().verifyOtp(
                      email: email,
                      code: otp,
                    );
                    if (!context.mounted) return;
                    Navigator.pop(context);
                    final user = data['user'] as Map<String, dynamic>;
                    await SessionStore.saveTokens(
                      data['access_token'] as String,
                      data['refresh_token'] as String,
                    );
                    await SessionStore.saveAccountEmail(
                      (user['email'] as String),
                    );
                    final name = SessionStore.displayNameFromEmail(
                        user['email'] as String);
                    await SessionStore.saveDisplayName(name);
                    if (!mounted) return;
                    try {
                      await PushService.initializeAfterLogin();
                    } catch (error) {
                      parentMessenger.showSnackBar(
                        const SnackBar(
                          content: Text(
                            'Login concluído, mas não foi possível ativar as notificações.',
                          ),
                        ),
                      );
                    }
                    if (!mounted) return;
                    parentMessenger.showSnackBar(
                      SnackBar(
                        content: Row(
                          children: [
                            const Icon(Icons.check_circle_outline,
                                color: Colors.white),
                            const SizedBox(width: 8),
                            Expanded(
                                child: Text('Bem-vindo ao Reclame Já, $name!')),
                          ],
                        ),
                        backgroundColor: ReclameJaColors.secondaryEmerald,
                      ),
                    );
                    parentNavigator.pushReplacement(
                      MaterialPageRoute(
                        builder: (context) => HomeShell(
                          isVisitor: false,
                          userName: name,
                        ),
                      ),
                    );
                  } catch (error) {
                    if (!context.mounted) return;
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(error.toString()),
                        backgroundColor: ReclameJaColors.alertRed,
                      ),
                    );
                  }
                },
                child: const Text('Confirmar entrada'),
              ),
            ],
          ),
        );
      },
    );
  }

  void _loginWithGoogle() {
    if (!_acceptedTerms || !_confirmedAge) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
              'Por favor, aceite os termos e confirme sua idade antes de continuar.'),
          backgroundColor: ReclameJaColors.alertRed,
        ),
      );
      return;
    }

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text(
          'Login com Google ainda não está configurado. Use o acesso por e-mail.',
        ),
        backgroundColor: ReclameJaColors.alertRed,
      ),
    );
  }

  void _exploreAsVisitor() {
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(
        builder: (context) =>
            const HomeShell(isVisitor: true, userName: 'Visitante'),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Logo/Header
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 8.0),
                child: Row(
                  children: [
                    Text(
                      'Reclame Já',
                      style: textTheme.headlineMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: ReclameJaColors.textDark,
                      ),
                    ),
                  ],
                ),
              ),

              // Hero section
              Container(
                height: 140,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(16),
                  image: const DecorationImage(
                    image: AssetImage('assets/images/inicial.jpg'),
                    fit: BoxFit.cover,
                  ),
                ),
                child: Container(
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(16),
                    gradient: LinearGradient(
                      begin: Alignment.bottomCenter,
                      end: Alignment.topCenter,
                      colors: [
                        Colors.black.withValues(alpha: 0.15),
                        Colors.transparent,
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // Title and Value Proposition (Solid High Contrast Card)
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: const Color(0xFF101828),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Viu um problema?',
                      style: GoogleFonts.spaceGrotesk(
                        fontSize: 26,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                        height: 1.2,
                      ),
                    ),
                    Text(
                      'Sua voz chega a quem pode resolver.',
                      style: GoogleFonts.spaceGrotesk(
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                        color: ReclameJaColors.primaryYellow,
                        height: 1.2,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Ajude a cuidar das praças, iluminação e calçadas. Transforme sua rua de forma rápida, colaborativa e 100% transparente.',
                      style: GoogleFonts.hankenGrotesk(
                        fontSize: 14,
                        color: Colors.white.withValues(alpha: 0.9),
                        height: 1.4,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              // Horizontal scroll benefits
              SizedBox(
                height: 115,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  itemCount: _benefits.length,
                  separatorBuilder: (context, index) =>
                      const SizedBox(width: 12),
                  itemBuilder: (context, index) {
                    final b = _benefits[index];
                    return Container(
                      width: MediaQuery.of(context).size.width * 0.78,
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: ReclameJaColors.surfaceBright,
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(
                          color: ReclameJaColors.borderSlate,
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: ReclameJaColors.textDark
                                .withValues(alpha: 0.03),
                            blurRadius: 4,
                            offset: const Offset(0, 2),
                          ),
                        ],
                      ),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Container(
                            padding: const EdgeInsets.all(10),
                            decoration: BoxDecoration(
                              color: b['bg'],
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Icon(
                              b['icon'],
                              color: b['fg'],
                              size: 24,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  b['title'],
                                  style: textTheme.titleMedium?.copyWith(
                                    fontWeight: FontWeight.bold,
                                    fontSize: 14,
                                    color: ReclameJaColors.textDark,
                                  ),
                                ),
                                const SizedBox(height: 2),
                                Expanded(
                                  child: Text(
                                    b['desc'],
                                    style: textTheme.bodySmall?.copyWith(
                                      color: ReclameJaColors.textMuted,
                                      height: 1.3,
                                    ),
                                    maxLines: 2,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ),
              const SizedBox(height: 20),

              // Consent & GDPR Controls
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: ReclameJaColors.surfaceLow,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Column(
                  children: [
                    // Consent Checkbox
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        SizedBox(
                          height: 24,
                          width: 24,
                          child: Checkbox(
                            value: _acceptedTerms,
                            activeColor: ReclameJaColors.secondaryEmerald,
                            onChanged: (val) {
                              setState(() {
                                _acceptedTerms = val ?? false;
                              });
                            },
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            'Li e aceito os Termos de Uso e Política de Privacidade.',
                            style: textTheme.bodySmall?.copyWith(
                              color: ReclameJaColors.textDark,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    // Age confirmation Checkbox
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        SizedBox(
                          height: 24,
                          width: 24,
                          child: Checkbox(
                            value: _confirmedAge,
                            activeColor: ReclameJaColors.secondaryEmerald,
                            onChanged: (val) {
                              setState(() {
                                _confirmedAge = val ?? false;
                              });
                            },
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            'Confirmo que tenho 18 anos ou mais, de acordo com a política etária.',
                            style: textTheme.bodySmall?.copyWith(
                              color: ReclameJaColors.textDark,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              // Login Actions
              // 1. Email button (Alert yellow)
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: ReclameJaColors.primaryYellow,
                  foregroundColor: ReclameJaColors.textDark,
                  elevation: 1,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
                onPressed: _showEmailLoginSheet,
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(Icons.mail_outline, size: 20),
                    const SizedBox(width: 8),
                    Text(
                      'Entrar com e-mail',
                      style: textTheme.labelLarge?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: ReclameJaColors.textDark,
                        fontSize: 15,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),

              // 2. Google Login button
              OutlinedButton(
                style: OutlinedButton.styleFrom(
                  backgroundColor: ReclameJaColors.surfaceBright,
                  foregroundColor: ReclameJaColors.textDark,
                  minimumSize: const Size.fromHeight(52),
                  side: const BorderSide(color: ReclameJaColors.borderSlate),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
                onPressed: _loginWithGoogle,
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    // Simulated Google SVG icon in a small container
                    Container(
                      width: 18,
                      height: 18,
                      alignment: Alignment.center,
                      child: const Icon(Icons.g_mobiledata,
                          color: Colors.blue, size: 28),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      'Continuar com Google',
                      style: textTheme.labelLarge?.copyWith(
                        fontWeight: FontWeight.bold,
                        fontSize: 15,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),

              // 3. Visitor Entry Button
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFFF2FBF5),
                  foregroundColor: ReclameJaColors.secondaryEmerald,
                  side: const BorderSide(color: Color(0xFFBBEFCE), width: 1.2),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
                onPressed: _exploreAsVisitor,
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(Icons.travel_explore,
                        size: 20, color: ReclameJaColors.secondaryEmerald),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Explorar chamados do bairro sem cadastro',
                        style: textTheme.labelLarge?.copyWith(
                          fontWeight: FontWeight.bold,
                          color: ReclameJaColors.secondaryEmerald,
                          fontSize: 13,
                        ),
                        textAlign: TextAlign.center,
                        maxLines: 2,
                        overflow: TextOverflow.visible,
                      ),
                    ),
                    const Icon(Icons.arrow_forward,
                        size: 16, color: ReclameJaColors.secondaryEmerald),
                  ],
                ),
              ),
              const SizedBox(height: 24),

              // LGPD privacy summary footer
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: ReclameJaColors.surfaceLow,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.lock,
                            size: 14, color: ReclameJaColors.textMuted),
                        const SizedBox(width: 6),
                        Text(
                          'Privacidade & Transparência',
                          style: textTheme.labelSmall?.copyWith(
                            fontWeight: FontWeight.bold,
                            color: ReclameJaColors.textMuted,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Seus dados estão protegidos conforme a LGPD (Lei 13.709/18). Usamos sua localização unicamente para mapear o local da zeladoria pública.',
                      style: textTheme.bodySmall?.copyWith(
                        color: ReclameJaColors.textMuted,
                        fontSize: 11,
                        height: 1.4,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),

              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  TextButton(
                    onPressed: () {
                      _showDialog('Termos de Uso',
                          'Termos de Uso oficiais do Reclame Já para engajamento e transparência cidadã.');
                    },
                    child: Text(
                      'Termos de Uso',
                      style: textTheme.bodySmall
                          ?.copyWith(decoration: TextDecoration.underline),
                    ),
                  ),
                  const Text('•',
                      style: TextStyle(color: ReclameJaColors.surfaceDim)),
                  TextButton(
                    onPressed: () {
                      _showDialog('Política de Privacidade',
                          'Política de Privacidade oficial de acordo com a LGPD (Lei 13.709/18). Seus dados estão seguros.');
                    },
                    child: Text(
                      'Política de Privacidade',
                      style: textTheme.bodySmall
                          ?.copyWith(decoration: TextDecoration.underline),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
            ],
          ),
        ),
      ),
    );
  }

  void _showDialog(String title, String content) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title,
            style: GoogleFonts.spaceGrotesk(fontWeight: FontWeight.bold)),
        content: Text(content, style: GoogleFonts.hankenGrotesk()),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Fechar',
                style: TextStyle(color: ReclameJaColors.secondaryEmerald)),
          ),
        ],
      ),
    );
  }
}
