import 'dart:math';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../app_theme.dart';
import '../services/report_store.dart';
import 'post_send_confirmation_screen.dart';

class NewReportWizard extends StatefulWidget {
  const NewReportWizard({super.key});

  @override
  State<NewReportWizard> createState() => _NewReportWizardState();
}

class _NewReportWizardState extends State<NewReportWizard> {
  int _currentStep = 1; // Steps: 1 (Foto), 2 (Local), 3 (Relato), 4 (Triagem)
  bool _isOfflineSimulated = false;
  bool _isAnonymous = false;
  
  // Form fields state
  String? _attachedPhotoUrl;
  final _referencePointController = TextEditingController(text: 'Em frente à padaria Estrela');
  final _descriptionController = TextEditingController(
    text: 'Grande buraco aberto na pista da direita após a chuva forte, oferecendo risco de queda a ciclistas e pedestres no cruzamento.'
  );
  String _selectedCategory = 'Risco Urbano';
  String _selectedSubcategory = 'Pavimentação';
  
  final List<Map<String, String>> _categories = [
    {'name': 'Pavimentação', 'group': 'Risco Urbano', 'icon': 'add_road'},
    {'name': 'Iluminação', 'group': 'Risco Urbano', 'icon': 'lightbulb'},
    {'name': 'Poda e Árvores', 'group': 'Risco Urbano', 'icon': 'park'},
    {'name': 'Água e Esgoto', 'group': 'Risco Urbano', 'icon': 'water_drop'},
    {'name': 'Ônibus e Paradas', 'group': 'Transporte', 'icon': 'directions_bus'},
    {'name': 'Atendimento UBS', 'group': 'Saúde', 'icon': 'local_hospital'},
  ];

  @override
  void dispose() {
    _referencePointController.dispose();
    _descriptionController.dispose();
    super.dispose();
  }

  void _nextStep() {
    if (_currentStep == 1 && _attachedPhotoUrl == null) {
      // Allow moving forward, but show warning that adding a photo is recommended
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Foto anexada com sucesso!')),
      );
    }
    
    if (_currentStep < 4) {
      setState(() {
        _currentStep++;
      });
    } else {
      _submitReport();
    }
  }

  void _prevStep() {
    if (_currentStep > 1) {
      setState(() {
        _currentStep--;
      });
    } else {
      Navigator.pop(context);
    }
  }

  void _attachMockPhoto() {
    setState(() {
      _attachedPhotoUrl = 'https://lh3.googleusercontent.com/aida-public/AB6AXuC1P9782zS7dhsm2tuVBbWbTbojjFt_qcWz4XsSczl5xDq_xgPWENSA34I9avM7bJsl8oOuG7orUHsRsLbz6NTVM58wOHAhOAKHS2xBQMvAj1Me-zpXnfHjIlxEs0lZMG1covjr6viqFCSC6wanSmedpXDDZgFPAp--6bE1Ww89DbRUSHogvSfs4tA_VvNFa-MK3aBDcPvMNyOjVga-lyz9mAK-sC15p-rvKn6DKcH1';
    });
  }

  void _removePhoto() {
    setState(() {
      _attachedPhotoUrl = null;
    });
  }

  void _simulateVoiceDictation() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Row(
          children: [
            Icon(Icons.mic, color: Colors.white),
            SizedBox(width: 8),
            Text('Ouvindo... Fale o relato do problema.'),
          ],
        ),
        backgroundColor: ReclameJaColors.secondaryEmerald,
        duration: Duration(seconds: 2),
      ),
    );
    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) {
        setState(() {
          _descriptionController.text = 'Identifiquei um bueiro sem tampa exalando mau cheiro e gerando risco de queda para crianças próximo à escola.';
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Ditado concluído com sucesso!'),
            backgroundColor: ReclameJaColors.secondaryEmerald,
          ),
        );
      }
    });
  }

  void _submitReport() {
    final title = _descriptionController.text.length > 40 
        ? '${_descriptionController.text.substring(0, 38)}...' 
        : _descriptionController.text;
        
    final randomDigits = Random().nextInt(9000) + 1000;
    final protocol = _isOfflineSimulated 
        ? 'LOCAL-${Random().nextInt(89999999) + 10000000}'
        : '#CV-2026-$randomDigits';

    final newReport = Report(
      id: protocol,
      title: title.isNotEmpty ? title : 'Chamado de Zeladoria Urbana',
      description: _descriptionController.text,
      location: 'Rua das Palmeiras, 342',
      details: '${_referencePointController.text.isNotEmpty ? "${_referencePointController.text}, " : ""}Jardim das Flores, São Paulo - SP',
      category: _selectedCategory,
      subcategory: _selectedSubcategory,
      status: 'Recebido',
      organ: _getOrganForCategory(_selectedCategory, _selectedSubcategory),
      confirmationCount: 1,
      isUserConfirmed: true,
      clientCreatedAt: '16/11/2026',
      isOffline: _isOfflineSimulated,
      imageUrl: _attachedPhotoUrl,
      forecast: 'Resposta prevista em até 48h úteis',
      timeline: [
        ReportEvent(
          title: 'Recebido',
          time: '16/11 às 17:04',
          desc: _isOfflineSimulated 
              ? 'Salvo localmente no aparelho no modo offline. Aguardando conexão para envio.'
              : 'Cadastrado e validado com sucesso pelo munícipe.',
          actor: 'Sistema',
        ),
      ],
      comments: [
        {
          'author': _isAnonymous ? 'Munícipe Anônimo' : 'Marina (Você)',
          'time': 'Agora mesmo',
          'text': _descriptionController.text,
          'isOfficial': 'false',
        }
      ],
    );

    // Save in shared database
    ReportStore().addReport(newReport);

    // Navigate to confirmation details screen
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(
        builder: (context) => PostSendConfirmationScreen(report: newReport),
      ),
    );
  }

  String _getOrganForCategory(String cat, String sub) {
    if (cat == 'Transporte') {
      return 'SPTrans / Operadora Distrital de Transportes';
    } else if (cat == 'Saúde') {
      return 'Ouvidoria de Saúde / Secretaria Municipal de Saúde';
    } else if (sub == 'Água e Esgoto') {
      return 'Sabesp / Central de Saneamento Distrital';
    } else {
      return 'Secretaria Municipal de Infraestrutura Urbana e Obras (SIURB)';
    }
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: _prevStep,
        ),
        title: const Text('Novo Reporte'),
        centerTitle: true,
        actions: [
          // Simulate offline switch
          Row(
            children: [
              const Icon(Icons.cloud_off, size: 18),
              const SizedBox(width: 4),
              Switch(
                value: _isOfflineSimulated,
                activeThumbColor: ReclameJaColors.primaryYellow,
                onChanged: (val) {
                  setState(() {
                    _isOfflineSimulated = val;
                  });
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text(_isOfflineSimulated 
                          ? 'Modo Offline Ativado! O reporte gerará protocolo provisório local.' 
                          : 'Modo Online Restaurado!'),
                      backgroundColor: _isOfflineSimulated ? Colors.orange : ReclameJaColors.secondaryEmerald,
                    ),
                  );
                },
              ),
            ],
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 12.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // OFFLINE BANNER (if simulated)
            if (_isOfflineSimulated)
              Container(
                margin: const EdgeInsets.only(bottom: 16),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: ReclameJaColors.greenContainer,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.cloud_off, color: ReclameJaColors.secondaryEmerald, size: 24),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                'Modo offline ativo',
                                style: textTheme.labelLarge?.copyWith(
                                  fontWeight: FontWeight.bold,
                                  color: ReclameJaColors.onGreenContainer,
                                ),
                              ),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                decoration: BoxDecoration(
                                  color: Colors.white,
                                  borderRadius: BorderRadius.circular(999),
                                ),
                                child: Text(
                                  'Salvo localmente',
                                  style: textTheme.labelSmall?.copyWith(fontSize: 10, color: ReclameJaColors.onGreenContainer),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 4),
                          Text(
                            'Seu reporte será armazenado no aparelho e enviado automaticamente assim que a conexão retornar.',
                            style: textTheme.bodySmall?.copyWith(color: ReclameJaColors.onGreenContainer),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),

            // STEPPER PROGRESS
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: ReclameJaColors.surfaceBright,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: ReclameJaColors.borderSlate),
              ),
              child: Column(
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('Progresso do cadastro', style: textTheme.labelMedium),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: ReclameJaColors.primaryYellow,
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: Text(
                          'Passo $_currentStep de 4',
                          style: textTheme.labelSmall?.copyWith(fontWeight: FontWeight.bold),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  // Progress line
                  Row(
                    children: List.generate(4, (index) {
                      final stepNum = index + 1;
                      final isActive = stepNum == _currentStep;
                      final isCompleted = stepNum < _currentStep;
                      return Expanded(
                        child: Container(
                          height: 6,
                          margin: EdgeInsets.only(
                            right: index < 3 ? 6.0 : 0.0,
                          ),
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(999),
                            color: isCompleted
                                ? ReclameJaColors.secondaryEmerald
                                : isActive
                                    ? ReclameJaColors.primaryYellow
                                    : ReclameJaColors.surfaceDim,
                          ),
                        ),
                      );
                    }),
                  ),
                  const SizedBox(height: 10),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.flash_on, size: 14, color: ReclameJaColors.tertiaryBlue),
                      const SizedBox(width: 4),
                      Text(
                        'Passo a passo rápido • Leva menos de 1 minuto',
                        style: textTheme.bodySmall?.copyWith(color: ReclameJaColors.textMuted),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),

            // MAIN CONTENT FOR EACH STEP
            _buildStepContent(),
            const SizedBox(height: 24),

            // EMERGENCY CALLOUT WARNING
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: ReclameJaColors.errorContainer.withValues(alpha: 0.4),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: ReclameJaColors.errorContainer),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.emergency, color: ReclameJaColors.alertRed, size: 20),
                      const SizedBox(width: 8),
                      Text(
                        'Risco iminente à vida?',
                        style: textTheme.titleMedium?.copyWith(
                          color: ReclameJaColors.onErrorContainer,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Este aplicativo destina-se a manutenções urbanas programadas. Em emergências ativas com risco de desabamento ou acidentes graves, ligue imediatamente:',
                    style: textTheme.bodySmall?.copyWith(color: ReclameJaColors.onErrorContainer, height: 1.4),
                  ),
                  const SizedBox(height: 12),
                  // Emergency Quick Dial Links
                  const Row(
                    children: [
                      _EmergencyDialButton(label: 'Polícia 190', number: '190'),
                      SizedBox(width: 8),
                      _EmergencyDialButton(label: 'SAMU 192', number: '192'),
                      SizedBox(width: 8),
                      _EmergencyDialButton(label: 'Bombeiros 193', number: '193'),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.verified, size: 14, color: ReclameJaColors.secondaryEmerald),
                const SizedBox(width: 4),
                Text(
                  'Protocolo oficial gerado e atualizado pela Zeladoria.',
                  style: textTheme.bodySmall?.copyWith(color: ReclameJaColors.textMuted),
                ),
              ],
            ),
            const SizedBox(height: 80), // spacer for bottom action button
          ],
        ),
      ),
      bottomSheet: Container(
        padding: const EdgeInsets.all(16),
        decoration: const BoxDecoration(
          color: ReclameJaColors.surfaceBright,
          border: Border(top: BorderSide(color: ReclameJaColors.borderSlate)),
        ),
        child: ElevatedButton(
          style: ElevatedButton.styleFrom(
            backgroundColor: ReclameJaColors.primaryYellow,
            foregroundColor: ReclameJaColors.textDark,
            minimumSize: const Size.fromHeight(52),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          onPressed: _nextStep,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(_currentStep == 4 ? Icons.send : Icons.arrow_forward, size: 20),
              const SizedBox(width: 8),
              Text(
                _currentStep == 4 ? 'Enviar solicitação' : 'Continuar',
                style: textTheme.labelLarge?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: ReclameJaColors.textDark,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStepContent() {
    final textTheme = Theme.of(context).textTheme;
    
    switch (_currentStep) {
      case 1: // Foto do Problema
        return Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: ReclameJaColors.surfaceBright,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: ReclameJaColors.borderSlate),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('1. Foto do problema', style: textTheme.headlineSmall),
                        const SizedBox(height: 4),
                        Text(
                          'Ajuda os técnicos a identificarem a equipe e os materiais necessários.',
                          style: textTheme.bodySmall?.copyWith(color: ReclameJaColors.textMuted, height: 1.4),
                        ),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: ReclameJaColors.surfaceLow,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      _attachedPhotoUrl == null ? '0/3 fotos' : '1/3 fotos',
                      style: textTheme.labelSmall?.copyWith(color: ReclameJaColors.secondaryEmerald),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  if (_attachedPhotoUrl != null)
                    Expanded(
                      child: AspectRatio(
                        aspectRatio: 1,
                        child: Container(
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(12),
                            image: DecorationImage(
                              image: NetworkImage(_attachedPhotoUrl!),
                              fit: BoxFit.cover,
                            ),
                          ),
                          child: Stack(
                            children: [
                              Positioned(
                                top: 6,
                                right: 6,
                                child: GestureDetector(
                                  onTap: _removePhoto,
                                  child: Container(
                                    padding: const EdgeInsets.all(4),
                                    decoration: const BoxDecoration(
                                      color: Colors.white,
                                      shape: BoxShape.circle,
                                    ),
                                    child: const Icon(Icons.delete, color: ReclameJaColors.alertRed, size: 18),
                                  ),
                                ),
                              ),
                              Positioned(
                                bottom: 6,
                                left: 6,
                                child: Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: Colors.black.withValues(alpha: 0.6),
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                  child: const Row(
                                    children: [
                                      Icon(Icons.verified, color: Colors.green, size: 12),
                                      SizedBox(width: 4),
                                      Text('Anexada', style: TextStyle(color: Colors.white, fontSize: 10)),
                                    ],
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    )
                  else
                    Expanded(
                      child: GestureDetector(
                        onTap: _attachMockPhoto,
                        child: AspectRatio(
                          aspectRatio: 1,
                          child: Container(
                            decoration: BoxDecoration(
                              color: ReclameJaColors.surfaceLow,
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: ReclameJaColors.surfaceDim, style: BorderStyle.solid),
                            ),
                            child: const Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(Icons.add_a_photo, size: 36, color: ReclameJaColors.textMuted),
                                SizedBox(height: 8),
                                Text('Anexar Foto', style: TextStyle(fontWeight: FontWeight.bold, color: ReclameJaColors.textDark)),
                                Text('Máx. 3 imagens', style: TextStyle(fontSize: 10, color: ReclameJaColors.textMuted)),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: GestureDetector(
                      onTap: () {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('Selecione uma imagem da galeria...')),
                        );
                      },
                      child: AspectRatio(
                        aspectRatio: 1,
                        child: Container(
                          decoration: BoxDecoration(
                            color: ReclameJaColors.surfaceLow,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(color: ReclameJaColors.surfaceDim, style: BorderStyle.solid),
                          ),
                          child: const Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(Icons.photo_library_outlined, size: 36, color: ReclameJaColors.textMuted),
                              SizedBox(height: 8),
                              Text('Abrir Galeria', style: TextStyle(fontWeight: FontWeight.bold, color: ReclameJaColors.textDark)),
                              Text('Formatos aceitos', style: TextStyle(fontSize: 10, color: ReclameJaColors.textMuted)),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
              if (_attachedPhotoUrl != null) ...[
                const SizedBox(height: 12),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Row(
                      children: [
                        Icon(Icons.check_circle, color: ReclameJaColors.secondaryEmerald, size: 18),
                        SizedBox(width: 6),
                        Text('Evidência nítida e validada', style: TextStyle(color: ReclameJaColors.secondaryEmerald, fontWeight: FontWeight.bold, fontSize: 12)),
                      ],
                    ),
                    TextButton(
                      onPressed: _attachMockPhoto,
                      child: const Text('Substituir', style: TextStyle(color: ReclameJaColors.textDark, fontWeight: FontWeight.bold)),
                    ),
                  ],
                ),
              ],
            ],
          ),
        );

      case 2: // Onde está acontecendo?
        return Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: ReclameJaColors.surfaceBright,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: ReclameJaColors.borderSlate),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('2. Onde está acontecendo?', style: textTheme.headlineSmall),
              const SizedBox(height: 4),
              Text(
                'Ponto de localização capturado via sensor GPS ou ajustado manualmente.',
                style: textTheme.bodySmall?.copyWith(color: ReclameJaColors.textMuted, height: 1.4),
              ),
              const SizedBox(height: 16),
              // Mini Map Mock
              Container(
                height: 160,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(12),
                  color: ReclameJaColors.surfaceLow,
                  image: const DecorationImage(
                    image: NetworkImage('https://lh3.googleusercontent.com/aida-public/AB6AXuA_HwLqCBgJGhr02_7bMEOB--uJh1XuDKTkyjDc-uSQs38q1uhOgvpjmxsJ_Feg4rxaIe3CjZp_-KB_Ebxi8QA1E-tLsgWHHsIIzeyC6irDMMVXgcIrhb5e-JeY2HrrmuTso-UuYy4soM2H3JiewH1-CVp88qWZOFEqUCUNX-RCJKFRJmMpBMmkwZte-RCGg6_2QZj3zmvO1nWJAqiGt9nESj5YS_IScw4zmRWqcbAg'),
                    fit: BoxFit.cover,
                  ),
                ),
                child: Stack(
                  children: [
                    Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Container(
                            padding: const EdgeInsets.all(8),
                            decoration: const BoxDecoration(
                              color: ReclameJaColors.primaryYellow,
                              shape: BoxShape.circle,
                              boxShadow: [BoxShadow(color: Colors.black26, blurRadius: 4, offset: Offset(0, 2))],
                            ),
                            child: const Icon(Icons.location_on, color: ReclameJaColors.textDark, size: 20),
                          ),
                          const SizedBox(height: 4),
                          Container(
                            width: 12,
                            height: 4,
                            decoration: BoxDecoration(
                              color: Colors.black26,
                              borderRadius: BorderRadius.circular(99),
                            ),
                          ),
                        ],
                      ),
                    ),
                    Positioned(
                      bottom: 8,
                      right: 8,
                      child: ElevatedButton.icon(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: ReclameJaColors.primaryYellow,
                          foregroundColor: ReclameJaColors.textDark,
                          minimumSize: const Size(100, 36),
                          padding: const EdgeInsets.symmetric(horizontal: 10),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                        ),
                        onPressed: () {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Arraste o mapa para ajustar o pino.')),
                          );
                        },
                        icon: const Icon(Icons.my_location, size: 14),
                        label: const Text('Ajustar pino', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),
              // Address Row
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: ReclameJaColors.surfaceLow,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: const BoxDecoration(
                        color: ReclameJaColors.primaryYellow,
                        shape: BoxShape.circle,
                      ),
                      child: const Icon(Icons.pin_drop, color: ReclameJaColors.textDark, size: 18),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Rua das Palmeiras, 342 - Jardim das Flores',
                            style: textTheme.labelLarge?.copyWith(fontSize: 13, fontWeight: FontWeight.bold),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          const SizedBox(height: 2),
                          Row(
                            children: [
                              Text('São Paulo - SP', style: textTheme.bodySmall?.copyWith(color: ReclameJaColors.textMuted)),
                              const SizedBox(width: 6),
                              Container(width: 4, height: 4, decoration: const BoxDecoration(color: ReclameJaColors.textMuted, shape: BoxShape.circle)),
                              const SizedBox(width: 6),
                              const Icon(Icons.gps_fixed, size: 10, color: ReclameJaColors.tertiaryBlue),
                              const SizedBox(width: 4),
                              Text('Precisão ~5m', style: TextStyle(fontSize: 10, color: ReclameJaColors.tertiaryBlue, fontWeight: FontWeight.bold, fontFamily: GoogleFonts.jetBrainsMono().fontFamily)),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              // Reference point input
              Text('Ponto de referência (opcional)', style: textTheme.titleSmall),
              const SizedBox(height: 6),
              TextField(
                controller: _referencePointController,
                decoration: const InputDecoration(
                  prefixIcon: Icon(Icons.storefront, color: ReclameJaColors.textMuted),
                  hintText: 'Ex: Próximo à praça ou poste nº 12',
                ),
              ),
            ],
          ),
        );

      case 3: // O que você observou?
        return Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: ReclameJaColors.surfaceBright,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: ReclameJaColors.borderSlate),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('3. O que você observou?', style: textTheme.headlineSmall),
                        const SizedBox(height: 4),
                        Text(
                          'Descreva em detalhes o ocorrido.',
                          style: textTheme.bodySmall?.copyWith(color: ReclameJaColors.textMuted, height: 1.4),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.mic, color: ReclameJaColors.secondaryEmerald),
                    tooltip: 'Ditar por voz',
                    onPressed: _simulateVoiceDictation,
                  ),
                ],
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _descriptionController,
                maxLines: 5,
                decoration: const InputDecoration(
                  hintText: 'Ex: Grande buraco aberto na pista da direita após a chuva forte, oferecendo risco de queda...',
                ),
              ),
              const SizedBox(height: 10),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Row(
                    children: [
                      Icon(Icons.check_circle, color: ReclameJaColors.secondaryEmerald, size: 14),
                      SizedBox(width: 4),
                      Text('Boa descrição informada', style: TextStyle(color: ReclameJaColors.secondaryEmerald, fontSize: 11, fontWeight: FontWeight.bold)),
                    ],
                  ),
                  Text(
                    '${_descriptionController.text.length} / 300',
                    style: textTheme.bodySmall?.copyWith(color: ReclameJaColors.textMuted),
                  ),
                ],
              ),
            ],
          ),
        );

      case 4: // Triagem IA & Confirmação
        return Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: ReclameJaColors.surfaceBright,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: ReclameJaColors.borderSlate),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('4. Categoria do chamado', style: textTheme.headlineSmall),
              const SizedBox(height: 4),
              Text(
                'Nossa inteligência artificial analisa e direciona seu chamado ao órgão responsável.',
                style: textTheme.bodySmall?.copyWith(color: ReclameJaColors.textMuted, height: 1.4),
              ),
              const SizedBox(height: 16),

              // AI Suggestion Banner
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: ReclameJaColors.greenContainer,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: const Color(0xFFBBEFCE)),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(6),
                      decoration: const BoxDecoration(
                        color: ReclameJaColors.secondaryEmerald,
                        shape: BoxShape.circle,
                      ),
                      child: const Icon(Icons.auto_awesome, color: Colors.white, size: 16),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                'Sugestão IA • Reclame Já',
                                style: textTheme.labelLarge?.copyWith(
                                  fontWeight: FontWeight.bold,
                                  color: ReclameJaColors.onGreenContainer,
                                ),
                              ),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1.5),
                                decoration: BoxDecoration(
                                  color: ReclameJaColors.primaryYellow,
                                  borderRadius: BorderRadius.circular(999),
                                ),
                                child: Text(
                                  '98% certeza',
                                  style: textTheme.labelSmall?.copyWith(fontSize: 9, fontWeight: FontWeight.bold),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 4),
                          RichText(
                            text: TextSpan(
                              style: textTheme.bodySmall?.copyWith(color: ReclameJaColors.textDark),
                              children: [
                                const TextSpan(text: 'Identificamos o tema '),
                                TextSpan(
                                  text: '$_selectedCategory - $_selectedSubcategory',
                                  style: const TextStyle(fontWeight: FontWeight.bold),
                                ),
                                const TextSpan(text: ' a partir do relato fotográfico e descritivo.'),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              // Categories Grid
              GridView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 2,
                  crossAxisSpacing: 8,
                  mainAxisSpacing: 8,
                  childAspectRatio: 2.8,
                ),
                itemCount: _categories.length,
                itemBuilder: (context, index) {
                  final cat = _categories[index];
                  final isSelected = cat['group'] == _selectedCategory && cat['name'] == _selectedSubcategory;
                  
                  return Material(
                    color: isSelected ? ReclameJaColors.primaryYellow : ReclameJaColors.surfaceLow,
                    borderRadius: BorderRadius.circular(12),
                    child: InkWell(
                      borderRadius: BorderRadius.circular(12),
                      onTap: () {
                        setState(() {
                          _selectedCategory = cat['group']!;
                          _selectedSubcategory = cat['name']!;
                        });
                      },
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 12.0),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Expanded(
                              child: Row(
                                children: [
                                  Icon(
                                    _getIconData(cat['icon']!),
                                    color: ReclameJaColors.textDark,
                                    size: 18,
                                  ),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: Text(
                                      cat['name']!,
                                      style: textTheme.labelMedium?.copyWith(
                                        fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                                        color: ReclameJaColors.textDark,
                                      ),
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            if (isSelected)
                              const Icon(Icons.check, color: ReclameJaColors.textDark, size: 16),
                          ],
                        ),
                      ),
                    ),
                  );
                },
              ),
              const SizedBox(height: 20),

              // Privacy & Anonymity Trigger
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: ReclameJaColors.surfaceLow,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: ReclameJaColors.borderSlate),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.security, color: ReclameJaColors.secondaryEmerald, size: 24),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Reportar anonimamente', style: textTheme.labelLarge?.copyWith(fontWeight: FontWeight.bold)),
                          const SizedBox(height: 2),
                          Text(
                            'Seus dados cadastrais não ficarão visíveis para a comunidade nem para as equipes operacionais. O protocolo continuará vinculado à sua conta.',
                            style: textTheme.bodySmall?.copyWith(color: ReclameJaColors.textMuted, height: 1.3),
                          ),
                        ],
                      ),
                    ),
                    Switch(
                      value: _isAnonymous,
                      activeThumbColor: ReclameJaColors.secondaryEmerald,
                      onChanged: (val) {
                        setState(() {
                          _isAnonymous = val;
                        });
                      },
                    ),
                  ],
                ),
              ),
            ],
          ),
        );
      default:
        return const SizedBox();
    }
  }

  IconData _getIconData(String name) {
    switch (name) {
      case 'add_road':
        return Icons.add_road;
      case 'lightbulb':
        return Icons.lightbulb;
      case 'park':
        return Icons.park;
      case 'water_drop':
        return Icons.water_drop;
      case 'directions_bus':
        return Icons.directions_bus;
      case 'local_hospital':
        return Icons.local_hospital;
      default:
        return Icons.help_outline;
    }
  }
}

class _EmergencyDialButton extends StatelessWidget {
  final String label;
  final String number;

  const _EmergencyDialButton({required this.label, required this.number});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: OutlinedButton(
        style: OutlinedButton.styleFrom(
          backgroundColor: Colors.white,
          foregroundColor: ReclameJaColors.alertRed,
          side: const BorderSide(color: ReclameJaColors.alertRed, width: 1.2),
          padding: const EdgeInsets.symmetric(vertical: 8),
          minimumSize: const Size(60, 40),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        ),
        onPressed: () {
          showDialog(
            context: context,
            builder: (context) => AlertDialog(
              title: Text('Ligando para $label', style: const TextStyle(fontWeight: FontWeight.bold)),
              content: Text('Dispositivo efetuando chamada simulada de emergência para o número de suporte vital $number.'),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Desconectar', style: TextStyle(color: ReclameJaColors.alertRed)),
                ),
              ],
            ),
          );
        },
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.call, size: 12),
            const SizedBox(width: 4),
            Text(label, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold)),
          ],
        ),
      ),
    );
  }
}
