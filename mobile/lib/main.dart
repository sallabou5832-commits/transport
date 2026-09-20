import 'package:flutter/widgets.dart';

import 'app.dart';
import 'config.dart';
import 'services.dart';
import 'ui/config_error_app.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  try {
    runApp(TransportApp(services: await AppServices.create()));
  } on ConfigurationException catch (e) {
    runApp(ConfigErrorApp(message: e.message));
  }
}
