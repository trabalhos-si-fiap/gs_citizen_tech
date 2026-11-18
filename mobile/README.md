# Mobile - Flutter

Aplicativo do cidadão do Reclame Já. Exige Flutter 3.44 ou superior (versão
travada pelo `pubspec.lock`).

## Executar

```bash
flutter pub get
flutter run --dart-define=API_BASE_URL=http://<ip-da-maquina>:8000
```

Com o stack Docker no ar (`docker compose up -d` na raiz), a API responde em
`http://127.0.0.1:8000`. Em emulador Android use `http://10.0.2.2:8000`.

## Testes

```bash
flutter analyze
flutter test
```

Sem Flutter instalado, rode pela mesma imagem usada no CI:

```bash
docker run --rm -v "$PWD:/app" -w /app ghcr.io/cirruslabs/flutter:3.44.0 \
  sh -c "flutter pub get --enforce-lockfile && flutter analyze && flutter test"
```

## Mapa e feed públicos

O mapa (`lib/screens/tabs/map_tab.dart`) e o feed
(`lib/screens/tabs/feed_tab.dart`) consomem `GET /v1/reports/nearby` por meio de
`lib/services/nearby_service.dart`, sem enviar token. Os tiles vêm do
OpenStreetMap público, aceitável para desenvolvimento e demonstração, mas não
para produção: troque `osmTileUrl` por um provedor próprio ou contratado.
