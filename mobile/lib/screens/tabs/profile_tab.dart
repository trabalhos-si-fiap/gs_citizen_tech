import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../app_theme.dart';
import '../../services/api_client.dart';
import '../../services/push_service.dart';
import '../../services/session_store.dart';
import '../welcome_screen.dart';

class ProfileTab extends StatelessWidget {
  final bool isVisitor;
  final String userName;

  const ProfileTab({
    super.key,
    required this.isVisitor,
    required this.userName,
  });

  Future<void> _exportDataAsJson(BuildContext context) async {
    if (SessionStore.accessToken == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Faça login para exportar os dados reais pela API.'),
        ),
      );
      return;
    }

    try {
      final data = await ApiClient().exportMyData();
      final jsonText = const JsonEncoder.withIndent('  ').convert(data);
      if (!context.mounted) return;
      final messenger = ScaffoldMessenger.of(context);
      showDialog(
        context: context,
        builder: (context) => AlertDialog(
          title: Row(
            children: [
              const Icon(Icons.download,
                  color: ReclameJaColors.secondaryEmerald),
              const SizedBox(width: 8),
              Text('Exportar Dados (LGPD)',
                  style: GoogleFonts.spaceGrotesk(
                      fontWeight: FontWeight.bold, fontSize: 16)),
            ],
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'Seus dados pessoais e histórico de chamados foram compilados em um arquivo estruturado JSON de acordo com a LGPD.',
                style: TextStyle(fontSize: 12, height: 1.4),
              ),
              const SizedBox(height: 12),
              Container(
                constraints: const BoxConstraints(maxHeight: 160),
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: ReclameJaColors.surfaceLow,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: SingleChildScrollView(
                  child: Text(
                    jsonText,
                    style: GoogleFonts.jetBrainsMono(
                        fontSize: 10, color: ReclameJaColors.textDark),
                  ),
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () async {
                await Clipboard.setData(ClipboardData(text: jsonText));
                if (!context.mounted) return;
                Navigator.pop(context);
                messenger.showSnackBar(
                  const SnackBar(
                      content:
                          Text('JSON copiado para a área de transferência.')),
                );
              },
              child: const Text('Fechar',
                  style: TextStyle(color: ReclameJaColors.textMuted)),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: ReclameJaColors.secondaryEmerald,
                foregroundColor: Colors.white,
                minimumSize: const Size(100, 40),
              ),
              onPressed: () => Navigator.pop(context),
              child: const Text('Copiar JSON'),
            ),
          ],
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
  }

  void _confirmAccountDeletion(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Row(
          children: [
            const Icon(Icons.warning, color: ReclameJaColors.alertRed),
            const SizedBox(width: 8),
            Text('Excluir Conta?',
                style: GoogleFonts.spaceGrotesk(
                    fontWeight: FontWeight.bold, fontSize: 18)),
          ],
        ),
        content: const Text(
          'Esta ação é irreversível. Seus dados cadastrais (nome, e-mail e cookies) serão apagados permanentemente de nossa base central de acordo com a LGPD. Suas ocorrências já encaminhadas à prefeitura permanecerão disponíveis para acompanhamento de forma 100% anonimizada.',
          style: TextStyle(fontSize: 13, height: 1.4),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancelar',
                style: TextStyle(
                    color: ReclameJaColors.textMuted,
                    fontWeight: FontWeight.bold)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: ReclameJaColors.alertRed,
              foregroundColor: Colors.white,
            ),
            onPressed: () async {
              Navigator.pop(context);
              if (SessionStore.accessToken == null) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Faça login para excluir a conta pela API.'),
                  ),
                );
                return;
              }
              try {
                await PushService.removeCurrentDevice();
                await ApiClient().deleteAccount();
                await SessionStore.clear();
                await PushService.dispose();
                if (!context.mounted) return;
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text(
                        'Conta excluída com sucesso de acordo com a LGPD.'),
                    backgroundColor: ReclameJaColors.alertRed,
                  ),
                );
                Navigator.pushReplacement(
                  context,
                  MaterialPageRoute(
                      builder: (context) => const WelcomeScreen()),
                );
              } catch (error) {
                if (!context.mounted) return;
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text(error.toString())),
                );
              }
            },
            child: const Text('Confirmar exclusão'),
          ),
        ],
      ),
    );
  }

  void _signOut(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Sair do Aplicativo',
            style: GoogleFonts.spaceGrotesk(fontWeight: FontWeight.bold)),
        content: const Text(
            'Deseja realmente desconectar e encerrar sua sessão ativa no Voz Cidadã?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Permanecer',
                style: TextStyle(color: ReclameJaColors.textMuted)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: ReclameJaColors.primaryYellow,
              foregroundColor: ReclameJaColors.textDark,
            ),
            onPressed: () async {
              Navigator.pop(context);
              try {
                await PushService.removeCurrentDevice();
              } catch (error) {
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text(
                        'Não foi possível remover o dispositivo das notificações. Confira sua conexão.',
                      ),
                      backgroundColor: ReclameJaColors.alertRed,
                    ),
                  );
                }
              }
              await SessionStore.clear();
              await PushService.dispose();
              if (!context.mounted) return;
              Navigator.pushReplacement(
                context,
                MaterialPageRoute(builder: (context) => const WelcomeScreen()),
              );
            },
            child: const Text('Desconectar'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    if (isVisitor) {
      return _buildVisitorProfileView(context);
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Meu Perfil'),
        centerTitle: true,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // User Meta Header Card
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: ReclameJaColors.surfaceBright,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: ReclameJaColors.borderSlate),
              ),
              child: Row(
                children: [
                  const CircleAvatar(
                    radius: 30,
                    backgroundColor: ReclameJaColors.primaryYellow,
                    child: Text(
                      'MS',
                      style: TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 20,
                          color: ReclameJaColors.textDark),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          userName,
                          style: textTheme.titleLarge
                              ?.copyWith(fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          SessionStore.accountEmail ?? '',
                          style: textTheme.bodySmall
                              ?.copyWith(color: ReclameJaColors.textMuted),
                        ),
                        const SizedBox(height: 6),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: const Color(0xFFF1F5F9),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(
                            'Consentimento Ativo: v1.0.2',
                            style: GoogleFonts.jetBrainsMono(
                                fontSize: 10,
                                color: ReclameJaColors.textMuted,
                                fontWeight: FontWeight.bold),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),

            // Settings Categories
            Text('LGPD & Privacidade',
                style: textTheme.titleMedium
                    ?.copyWith(fontWeight: FontWeight.bold)),
            const SizedBox(height: 10),
            Material(
              color: ReclameJaColors.surfaceBright,
              borderRadius: BorderRadius.circular(16),
              child: Container(
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: ReclameJaColors.borderSlate),
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(16),
                  child: Column(
                    children: [
                      ListTile(
                        leading: const Icon(Icons.download,
                            color: ReclameJaColors.secondaryEmerald),
                        title: const Text('Exportar meus dados',
                            style: TextStyle(
                                fontSize: 14, fontWeight: FontWeight.bold)),
                        subtitle: const Text(
                            'Portabilidade de informações em formato JSON',
                            style: TextStyle(fontSize: 11)),
                        trailing: const Icon(Icons.chevron_right, size: 16),
                        onTap: () => _exportDataAsJson(context),
                      ),
                      const Divider(height: 1, indent: 16, endIndent: 16),
                      ListTile(
                        leading: const Icon(Icons.delete_forever,
                            color: ReclameJaColors.alertRed),
                        title: const Text('Excluir minha conta',
                            style: TextStyle(
                                fontSize: 14,
                                fontWeight: FontWeight.bold,
                                color: ReclameJaColors.alertRed)),
                        subtitle: const Text(
                            'Apagar dados pessoais sob as regras da LGPD',
                            style: TextStyle(fontSize: 11)),
                        trailing: const Icon(Icons.chevron_right,
                            size: 16, color: ReclameJaColors.alertRed),
                        onTap: () => _confirmAccountDeletion(context),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(height: 24),

            Text('Termos Legais',
                style: textTheme.titleMedium
                    ?.copyWith(fontWeight: FontWeight.bold)),
            const SizedBox(height: 10),
            Material(
              color: ReclameJaColors.surfaceBright,
              borderRadius: BorderRadius.circular(16),
              child: Container(
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: ReclameJaColors.borderSlate),
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(16),
                  child: Column(
                    children: [
                      ListTile(
                        leading: const Icon(Icons.description_outlined,
                            color: ReclameJaColors.textDark),
                        title: const Text('Termos de Uso',
                            style: TextStyle(
                                fontSize: 14, fontWeight: FontWeight.bold)),
                        trailing: const Icon(Icons.chevron_right, size: 16),
                        onTap: () {
                          _showDialog(context, 'Termos de Uso',
                              'Termos de Uso oficiais do Voz Cidadã. Comprometimento mútuo para melhorias na infraestrutura e transparência na zeladoria pública.');
                        },
                      ),
                      const Divider(height: 1, indent: 16, endIndent: 16),
                      ListTile(
                        leading: const Icon(Icons.lock_outline,
                            color: ReclameJaColors.textDark),
                        title: const Text('Política de Privacidade',
                            style: TextStyle(
                                fontSize: 14, fontWeight: FontWeight.bold)),
                        trailing: const Icon(Icons.chevron_right, size: 16),
                        onTap: () {
                          _showDialog(context, 'Política de Privacidade',
                              'Política de Privacidade regulamentada pela LGPD (Lei 13.709/18). Seus dados pessoais estão criptografados e seguros.');
                        },
                      ),
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(height: 32),

            // Logout Button
            OutlinedButton.icon(
              style: OutlinedButton.styleFrom(
                foregroundColor: ReclameJaColors.alertRed,
                side: const BorderSide(
                    color: ReclameJaColors.alertRed, width: 1.2),
                minimumSize: const Size.fromHeight(52),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16)),
              ),
              onPressed: () => _signOut(context),
              icon: const Icon(Icons.exit_to_app),
              label: const Text('Sair do Aplicativo',
                  style: TextStyle(fontWeight: FontWeight.bold)),
            ),
            const SizedBox(height: 12),
            const Center(
              child: Text(
                'Voz Cidadã v1.0.0 • Made with IBM Bob',
                style:
                    TextStyle(fontSize: 11, color: ReclameJaColors.textMuted),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildVisitorProfileView(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Meu Perfil'),
        centerTitle: true,
      ),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(32.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Container(
                padding: const EdgeInsets.all(16),
                decoration: const BoxDecoration(
                  color: ReclameJaColors.surfaceLow,
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.account_circle_outlined,
                    size: 64, color: ReclameJaColors.textMuted),
              ),
              const SizedBox(height: 24),
              Text(
                'Sua conta, sua Voz',
                style: textTheme.headlineMedium
                    ?.copyWith(fontSize: 22, fontWeight: FontWeight.bold),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 10),
              Text(
                'Você está navegando como visitante e seus dados não estão sendo salvos. Crie um perfil auditável para arquivar com segurança seus chamados de zeladoria, cobrar prazos e exportar relatórios pela LGPD.',
                style: textTheme.bodyMedium
                    ?.copyWith(color: ReclameJaColors.textMuted, height: 1.4),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 32),
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: ReclameJaColors.primaryYellow,
                  foregroundColor: ReclameJaColors.textDark,
                  minimumSize: const Size.fromHeight(52),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16)),
                ),
                onPressed: () {
                  Navigator.pushReplacement(
                    context,
                    MaterialPageRoute(
                        builder: (context) => const WelcomeScreen()),
                  );
                },
                child: const Text('Fazer Login ou Criar Perfil',
                    style: TextStyle(fontWeight: FontWeight.bold)),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showDialog(BuildContext context, String title, String content) {
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
