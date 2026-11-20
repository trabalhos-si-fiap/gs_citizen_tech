import 'dart:async';
import 'dart:io';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:geolocator/geolocator.dart';
import 'package:uuid/uuid.dart';
import 'package:image_picker/image_picker.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import '../app_theme.dart';
import '../services/report_store.dart';
import '../services/address_service.dart';
import '../services/api_client.dart';
import '../services/category_labels.dart';
import '../services/outbox_store.dart';
import '../services/session_store.dart';
import 'post_send_confirmation_screen.dart';

/// Limite do relato no app (a API aceita até 1000 caracteres).
const maxDescriptionLength = 300;

/// A API só aceita o reporte com foto ou com descrição.
bool reportHasContent({required bool hasPhoto, required String description}) =>
    hasPhoto || description.trim().isNotEmpty;

class NewReportWizard extends StatefulWidget {
  const NewReportWizard({super.key, this.positionSource, this.addressLookup});

  /// GPS do aparelho; os testes passam uma posição fixa.
  final Future<Position> Function()? positionSource;

  /// Endereço da posição capturada; padrão: [defaultAddressLookup].
  final AddressLookup? addressLookup;

  @override
  State<NewReportWizard> createState() => _NewReportWizardState();
}

class _NewReportWizardState extends State<NewReportWizard> {
  int _currentStep = 1; // Steps: 1 (Foto), 2 (Local), 3 (Relato), 4 (Triagem)
  bool _isOfflineSimulated = false;
  bool _isAnonymous = false;

  // Form fields state
  String? _attachedPhotoUrl;
  Uint8List? _attachedPhotoBytes;
  Position? _position;
  String? _address;
  bool _isLocating = false;
  final _referencePointController = TextEditingController();
  final _descriptionController = TextEditingController();
  bool _descriptionMissing = false;
  // Sem escolha (null), a IA classifica o reporte depois do envio.
  String? _selectedCategory;
  String? _selectedSubcategory;

  final List<Map<String, String>> _categories = [
    {'name': 'Pavimentação', 'group': 'Risco Urbano', 'icon': 'add_road'},
    {'name': 'Iluminação', 'group': 'Risco Urbano', 'icon': 'lightbulb'},
    {'name': 'Poda e Árvores', 'group': 'Risco Urbano', 'icon': 'park'},
    {'name': 'Água e Esgoto', 'group': 'Risco Urbano', 'icon': 'water_drop'},
    {
      'name': 'Ônibus e Paradas',
      'group': 'Transporte',
      'icon': 'directions_bus'
    },
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
      // A foto é opcional: segue, mas avisa que ela ajuda na avaliação.
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
              'Sem foto: anexar uma imagem ajuda a equipe a avaliar o problema.'),
        ),
      );
    }

    if (_currentStep == 3 &&
        !reportHasContent(
          hasPhoto: _attachedPhotoUrl != null,
          description: _descriptionController.text,
        )) {
      setState(() => _descriptionMissing = true);
      return;
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

  Future<void> _attachPhoto({
    ImageSource source = ImageSource.camera,
  }) async {
    try {
      final picked = await ImagePicker().pickImage(
        source: source,
        imageQuality: 85,
        maxWidth: 1600,
      );
      if (picked == null) return;
      final documents = await getApplicationDocumentsDirectory();
      final photoFile = await File(picked.path).copy(
        '${documents.path}/report_${const Uuid().v4()}.jpg',
      );
      final bytes = await photoFile.readAsBytes();
      final previousPath = _attachedPhotoUrl;
      if (!mounted) return;
      setState(() {
        _attachedPhotoBytes = bytes;
        _attachedPhotoUrl = photoFile.path;
      });
      if (previousPath != null) {
        final previousFile = File(previousPath);
        if (await previousFile.exists()) await previousFile.delete();
      }
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content:
              Text('Não foi possível anexar essa imagem. Tente novamente.'),
          backgroundColor: ReclameJaColors.alertRed,
        ),
      );
    }
  }

  Future<void> _removePhoto() async {
    final photoPath = _attachedPhotoUrl;
    setState(() {
      _attachedPhotoUrl = null;
      _attachedPhotoBytes = null;
    });
    try {
      if (photoPath != null) {
        final photoFile = File(photoPath);
        if (await photoFile.exists()) await photoFile.delete();
      }
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content:
                Text('Não foi possível remover o arquivo de imagem local.'),
            backgroundColor: ReclameJaColors.alertRed,
          ),
        );
      }
    }
  }

  Future<void> _captureLocation() async {
    setState(() => _isLocating = true);
    try {
      final position =
          await (widget.positionSource ?? _currentDevicePosition)();
      final address = await _addressOf(position);
      if (!mounted) return;
      setState(() {
        _position = position;
        _address = address;
      });
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            error is StateError
                ? error.message
                : 'Não foi possível obter sua localização. Tente novamente.',
          ),
          backgroundColor: ReclameJaColors.alertRed,
        ),
      );
    } finally {
      if (mounted) setState(() => _isLocating = false);
    }
  }

  /// Endereço legível da posição. Sem resposta em 5 s, ou com falha, segue
  /// sem endereço: o envio funciona e a tela mostra as coordenadas.
  Future<String?> _addressOf(Position position) async {
    try {
      return await (widget.addressLookup ?? defaultAddressLookup)
          .addressFor(position.latitude, position.longitude)
          .timeout(const Duration(seconds: 5));
    } catch (_) {
      return null;
    }
  }

  Future<Position> _currentDevicePosition() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      throw StateError('Ative o serviço de localização para continuar.');
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied ||
        permission == LocationPermission.deniedForever) {
      throw StateError('Permita o acesso à localização para registrar o local.');
    }
    return Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.high,
        timeLimit: Duration(seconds: 20),
      ),
    );
  }

  Future<void> _submitReport() async {
    final title = _descriptionController.text.length > 40
        ? '${_descriptionController.text.substring(0, 38)}...'
        : _descriptionController.text;

    if (SessionStore.accessToken == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Faça login antes de enviar o reporte.'),
          backgroundColor: ReclameJaColors.alertRed,
        ),
      );
      return;
    }
    if (_position == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Obtenha a localização do reporte antes de enviar.'),
          backgroundColor: ReclameJaColors.alertRed,
        ),
      );
      setState(() => _currentStep = 2);
      return;
    }

    final reportId = const Uuid().v4();
    final now = DateTime.now();
    final createdAt = now.toUtc().toIso8601String();
    // Sem categoria escolhida o campo não é enviado: a IA classifica sem o
    // palpite do app (que ela tenderia a repetir).
    final category = const {
      'Risco Urbano': 'risco_urbano',
      'Transporte': 'transporte_publico',
      'Saúde': 'saude_atendimento',
    }[_selectedCategory];
    final coordinates =
        formatCoordinates(_position!.latitude, _position!.longitude);
    final outboxPayload = <String, dynamic>{
      'id': reportId,
      'description': _descriptionController.text.trim(),
      'has_photo': _attachedPhotoBytes != null,
      'photo_path': _attachedPhotoUrl,
      if (category != null) 'category': category,
      'lat': _position!.latitude,
      'lon': _position!.longitude,
      'location_accuracy_m': _position!.accuracy,
      'anonymous': _isAnonymous,
      if (_address != null) 'address': _address,
      'client_created_at': createdAt,
    };
    var pendingSync = _isOfflineSimulated;
    String? apiProtocol;
    String? apiReportId;
    if (pendingSync) {
      await OutboxStore.enqueue(outboxPayload);
    } else {
      try {
        final created = await ApiClient().createReport(
          id: reportId,
          description: _descriptionController.text.trim(),
          lat: _position!.latitude,
          lon: _position!.longitude,
          locationAccuracyM: _position!.accuracy,
          anonymous: _isAnonymous,
          category: category,
          hasPhoto: _attachedPhotoBytes != null,
          clientCreatedAt: createdAt,
          address: _address,
        );
        apiProtocol = created['protocol'] as String?;
        apiReportId = created['id'] as String?;
        if (_attachedPhotoBytes != null &&
            created['upload'] is Map<String, dynamic>) {
          await ApiClient().uploadPhoto(
            reportId: apiReportId ?? reportId,
            upload: created['upload'] as Map<String, dynamic>,
            bytes: _attachedPhotoBytes!,
          );
        }
      } on SocketException {
        await OutboxStore.enqueue(outboxPayload);
        pendingSync = true;
      } on http.ClientException {
        await OutboxStore.enqueue(outboxPayload);
        pendingSync = true;
      } on TimeoutException {
        await OutboxStore.enqueue(outboxPayload);
        pendingSync = true;
      } catch (error) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(error.toString()),
            backgroundColor: ReclameJaColors.alertRed,
          ),
        );
        return;
      }
    }

    final randomDigits = Random().nextInt(9000) + 1000;
    final protocol = pendingSync
        ? 'LOCAL-${Random().nextInt(89999999) + 10000000}'
        : (apiProtocol ?? '#CV-2026-$randomDigits');

    final newReport = Report(
      id: protocol,
      apiId: apiReportId ?? reportId,
      title: title.isNotEmpty ? title : 'Chamado de Zeladoria Urbana',
      description: _descriptionController.text,
      location: _address ?? coordinates,
      details: _referencePointController.text.trim(),
      category: _selectedCategory ?? labelForCategory(null),
      subcategory: _selectedSubcategory ?? '',
      status: 'Recebido',
      // Órgão e prazo vêm do encaminhamento feito pela API.
      organ: '',
      confirmationCount: 1,
      isUserConfirmed: true,
      clientCreatedAt: formatDateTime(now),
      isOffline: pendingSync,
      imageUrl: _attachedPhotoUrl,
      forecast: '',
      timeline: [
        ReportEvent(
          title: 'Recebido',
          time: formatDateTime(now),
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
    if (!mounted) return;
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(
        builder: (context) => PostSendConfirmationScreen(report: newReport),
      ),
    );
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
                      backgroundColor: _isOfflineSimulated
                          ? Colors.orange
                          : ReclameJaColors.secondaryEmerald,
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
                    const Icon(Icons.cloud_off,
                        color: ReclameJaColors.secondaryEmerald, size: 24),
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
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 8, vertical: 2),
                                decoration: BoxDecoration(
                                  color: Colors.white,
                                  borderRadius: BorderRadius.circular(999),
                                ),
                                child: Text(
                                  'Salvo localmente',
                                  style: textTheme.labelSmall?.copyWith(
                                      fontSize: 10,
                                      color: ReclameJaColors.onGreenContainer),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 4),
                          Text(
                            'Seu reporte será armazenado no aparelho e enviado automaticamente assim que a conexão retornar.',
                            style: textTheme.bodySmall?.copyWith(
                                color: ReclameJaColors.onGreenContainer),
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
                      Text('Progresso do cadastro',
                          style: textTheme.labelMedium),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: ReclameJaColors.primaryYellow,
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: Text(
                          'Passo $_currentStep de 4',
                          style: textTheme.labelSmall
                              ?.copyWith(fontWeight: FontWeight.bold),
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
                      const Icon(Icons.flash_on,
                          size: 14, color: ReclameJaColors.tertiaryBlue),
                      const SizedBox(width: 4),
                      Text(
                        'Passo a passo rápido • Leva menos de 1 minuto',
                        style: textTheme.bodySmall
                            ?.copyWith(color: ReclameJaColors.textMuted),
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
                      const Icon(Icons.emergency,
                          color: ReclameJaColors.alertRed, size: 20),
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
                    style: textTheme.bodySmall?.copyWith(
                        color: ReclameJaColors.onErrorContainer, height: 1.4),
                  ),
                  const SizedBox(height: 12),
                  // Emergency Quick Dial Links
                  const Row(
                    children: [
                      _EmergencyDialButton(label: 'Polícia 190', number: '190'),
                      SizedBox(width: 8),
                      _EmergencyDialButton(label: 'SAMU 192', number: '192'),
                      SizedBox(width: 8),
                      _EmergencyDialButton(
                          label: 'Bombeiros 193', number: '193'),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.verified,
                    size: 14, color: ReclameJaColors.secondaryEmerald),
                const SizedBox(width: 4),
                Text(
                  'Protocolo oficial gerado e atualizado pela Zeladoria.',
                  style: textTheme.bodySmall
                      ?.copyWith(color: ReclameJaColors.textMuted),
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
              Icon(_currentStep == 4 ? Icons.send : Icons.arrow_forward,
                  size: 20),
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
                        Text('1. Foto do problema',
                            style: textTheme.headlineSmall),
                        const SizedBox(height: 4),
                        Text(
                          'Ajuda os técnicos a identificarem a equipe e os materiais necessários.',
                          style: textTheme.bodySmall?.copyWith(
                              color: ReclameJaColors.textMuted, height: 1.4),
                        ),
                      ],
                    ),
                  ),
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: ReclameJaColors.surfaceLow,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      _attachedPhotoUrl == null ? '0/3 fotos' : '1/3 fotos',
                      style: textTheme.labelSmall
                          ?.copyWith(color: ReclameJaColors.secondaryEmerald),
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
                              image: MemoryImage(_attachedPhotoBytes!),
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
                                    child: const Icon(Icons.delete,
                                        color: ReclameJaColors.alertRed,
                                        size: 18),
                                  ),
                                ),
                              ),
                              Positioned(
                                bottom: 6,
                                left: 6,
                                child: Container(
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 6, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: Colors.black.withValues(alpha: 0.6),
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                  child: const Row(
                                    children: [
                                      Icon(Icons.verified,
                                          color: Colors.green, size: 12),
                                      SizedBox(width: 4),
                                      Text('Anexada',
                                          style: TextStyle(
                                              color: Colors.white,
                                              fontSize: 10)),
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
                        onTap: _attachPhoto,
                        child: AspectRatio(
                          aspectRatio: 1,
                          child: Container(
                            decoration: BoxDecoration(
                              color: ReclameJaColors.surfaceLow,
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(
                                  color: ReclameJaColors.surfaceDim,
                                  style: BorderStyle.solid),
                            ),
                            child: const Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(Icons.add_a_photo,
                                    size: 36, color: ReclameJaColors.textMuted),
                                SizedBox(height: 8),
                                Text('Anexar Foto',
                                    style: TextStyle(
                                        fontWeight: FontWeight.bold,
                                        color: ReclameJaColors.textDark)),
                                Text('Máx. 3 imagens',
                                    style: TextStyle(
                                        fontSize: 10,
                                        color: ReclameJaColors.textMuted)),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: GestureDetector(
                      onTap: () => _attachPhoto(source: ImageSource.gallery),
                      child: AspectRatio(
                        aspectRatio: 1,
                        child: Container(
                          decoration: BoxDecoration(
                            color: ReclameJaColors.surfaceLow,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(
                                color: ReclameJaColors.surfaceDim,
                                style: BorderStyle.solid),
                          ),
                          child: const Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(Icons.photo_library_outlined,
                                  size: 36, color: ReclameJaColors.textMuted),
                              SizedBox(height: 8),
                              Text('Abrir Galeria',
                                  style: TextStyle(
                                      fontWeight: FontWeight.bold,
                                      color: ReclameJaColors.textDark)),
                              Text('Formatos aceitos',
                                  style: TextStyle(
                                      fontSize: 10,
                                      color: ReclameJaColors.textMuted)),
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
                        Icon(Icons.check_circle,
                            color: ReclameJaColors.secondaryEmerald, size: 18),
                        SizedBox(width: 6),
                        Text('Evidência nítida e validada',
                            style: TextStyle(
                                color: ReclameJaColors.secondaryEmerald,
                                fontWeight: FontWeight.bold,
                                fontSize: 12)),
                      ],
                    ),
                    TextButton(
                      onPressed: _attachPhoto,
                      child: const Text('Substituir',
                          style: TextStyle(
                              color: ReclameJaColors.textDark,
                              fontWeight: FontWeight.bold)),
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
                style: textTheme.bodySmall
                    ?.copyWith(color: ReclameJaColors.textMuted, height: 1.4),
              ),
              const SizedBox(height: 16),
              // Mini Map Mock
              Container(
                height: 160,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(12),
                  color: ReclameJaColors.surfaceLow,
                ),
                child: Stack(
                  children: [
                    Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            _position == null
                                ? Icons.location_searching
                                : Icons.location_on,
                            color: ReclameJaColors.secondaryEmerald,
                            size: 44,
                          ),
                          const SizedBox(height: 6),
                          Text(
                            _position == null
                                ? 'Localização ainda não capturada'
                                : 'Localização capturada',
                            style: textTheme.labelMedium,
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
                          shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(20)),
                        ),
                        onPressed: _isLocating ? null : _captureLocation,
                        icon: _isLocating
                            ? const SizedBox(
                                width: 14,
                                height: 14,
                                child:
                                    CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Icon(Icons.my_location, size: 14),
                        label: Text(
                          _isLocating ? 'Localizando' : 'Capturar GPS',
                          style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
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
                      child: const Icon(Icons.pin_drop,
                          color: ReclameJaColors.textDark, size: 18),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            _position == null
                                ? 'Aguardando localização GPS'
                                : _address ??
                                    formatCoordinates(_position!.latitude,
                                        _position!.longitude),
                            style: textTheme.labelLarge?.copyWith(
                                fontSize: 13, fontWeight: FontWeight.bold),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                          const SizedBox(height: 2),
                          // Coordenadas só como detalhe, quando há endereço.
                          Text(
                            _position == null
                                ? 'Toque em Capturar GPS'
                                : [
                                    'Precisão ±${_position!.accuracy.toStringAsFixed(0)} m',
                                    if (_address != null)
                                      formatCoordinates(_position!.latitude,
                                          _position!.longitude),
                                  ].join(' • '),
                            style: textTheme.bodySmall?.copyWith(
                              color: ReclameJaColors.textMuted,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              // Reference point input
              Text('Ponto de referência (opcional)',
                  style: textTheme.titleSmall),
              const SizedBox(height: 6),
              TextField(
                controller: _referencePointController,
                decoration: const InputDecoration(
                  prefixIcon:
                      Icon(Icons.storefront, color: ReclameJaColors.textMuted),
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
              Text('3. O que você observou?', style: textTheme.headlineSmall),
              const SizedBox(height: 4),
              Text(
                'Descreva em detalhes o ocorrido.',
                style: textTheme.bodySmall
                    ?.copyWith(color: ReclameJaColors.textMuted, height: 1.4),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _descriptionController,
                maxLines: 5,
                inputFormatters: [
                  LengthLimitingTextInputFormatter(maxDescriptionLength),
                ],
                // Atualiza o contador e o indicador enquanto o munícipe digita.
                onChanged: (_) => setState(() => _descriptionMissing = false),
                decoration: InputDecoration(
                  hintText:
                      'Ex: Grande buraco aberto na pista da direita após a chuva forte, oferecendo risco de queda...',
                  errorText: _descriptionMissing
                      ? 'Descreva o que você observou ou anexe uma foto.'
                      : null,
                  errorMaxLines: 2,
                ),
              ),
              const SizedBox(height: 10),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  if (_descriptionController.text.trim().isEmpty)
                    const SizedBox.shrink()
                  else
                    const Row(
                      children: [
                        Icon(Icons.check_circle,
                            color: ReclameJaColors.secondaryEmerald, size: 14),
                        SizedBox(width: 4),
                        Text('Boa descrição informada',
                            style: TextStyle(
                                color: ReclameJaColors.secondaryEmerald,
                                fontSize: 11,
                                fontWeight: FontWeight.bold)),
                      ],
                    ),
                  Text(
                    '${_descriptionController.text.length} / $maxDescriptionLength',
                    style: textTheme.bodySmall
                        ?.copyWith(color: ReclameJaColors.textMuted),
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
                style: textTheme.bodySmall
                    ?.copyWith(color: ReclameJaColors.textMuted, height: 1.4),
              ),
              const SizedBox(height: 16),

              // Como a IA entra: depois do envio, com confirmação do munícipe.
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
                    const Icon(Icons.auto_awesome,
                        color: ReclameJaColors.secondaryEmerald, size: 20),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'Depois do envio, a IA classifica o reporte a partir do seu relato. Você confere e confirma a categoria na próxima tela.',
                        style: textTheme.bodySmall?.copyWith(
                            color: ReclameJaColors.onGreenContainer,
                            height: 1.4),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              _buildCategoryOption(
                label: 'Deixar a IA classificar',
                icon: Icons.auto_awesome,
                isSelected: _selectedCategory == null,
                onTap: () => setState(() {
                  _selectedCategory = null;
                  _selectedSubcategory = null;
                }),
              ),
              const SizedBox(height: 8),

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
                  final isSelected = cat['group'] == _selectedCategory &&
                      cat['name'] == _selectedSubcategory;

                  return _buildCategoryOption(
                    label: cat['name']!,
                    icon: _getIconData(cat['icon']!),
                    isSelected: isSelected,
                    onTap: () => setState(() {
                      _selectedCategory = cat['group']!;
                      _selectedSubcategory = cat['name']!;
                    }),
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
                    const Icon(Icons.security,
                        color: ReclameJaColors.secondaryEmerald, size: 24),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Reportar anonimamente',
                              style: textTheme.labelLarge
                                  ?.copyWith(fontWeight: FontWeight.bold)),
                          const SizedBox(height: 2),
                          Text(
                            'Seus dados cadastrais não ficarão visíveis para a comunidade nem para as equipes operacionais. O protocolo continuará vinculado à sua conta.',
                            style: textTheme.bodySmall?.copyWith(
                                color: ReclameJaColors.textMuted, height: 1.3),
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

  Widget _buildCategoryOption({
    required String label,
    required IconData icon,
    required bool isSelected,
    required VoidCallback onTap,
  }) {
    return Material(
      color: isSelected
          ? ReclameJaColors.primaryYellow
          : ReclameJaColors.surfaceLow,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
          child: Row(
            children: [
              Icon(icon, color: ReclameJaColors.textDark, size: 18),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  label,
                  style: Theme.of(context).textTheme.labelMedium?.copyWith(
                        fontWeight:
                            isSelected ? FontWeight.bold : FontWeight.normal,
                        color: ReclameJaColors.textDark,
                      ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              if (isSelected)
                const Icon(Icons.check,
                    color: ReclameJaColors.textDark, size: 16),
            ],
          ),
        ),
      ),
    );
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
              title: Text('Ligando para $label',
                  style: const TextStyle(fontWeight: FontWeight.bold)),
              content: Text(
                  'Dispositivo efetuando chamada simulada de emergência para o número de suporte vital $number.'),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Desconectar',
                      style: TextStyle(color: ReclameJaColors.alertRed)),
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
            // Três botões dividem a largura: o rótulo encolhe para caber.
            Flexible(
              child: FittedBox(
                fit: BoxFit.scaleDown,
                child: Text(label,
                    style: const TextStyle(
                        fontSize: 10, fontWeight: FontWeight.bold)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
