import 'package:flutter/widgets.dart';

import 'app.dart';
import 'services.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(TransportApp(services: await AppServices.create()));
}
