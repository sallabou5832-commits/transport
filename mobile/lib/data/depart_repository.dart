import '../api/api_client.dart';
import '../api/api_exception.dart';
import '../auth/app_user.dart';
import '../storage/cache_store.dart';
import 'loaded.dart';

/// Un départ proposé à la vente (avec le nom de sa ligne).
class DepartOption {
  const DepartOption({
    required this.id,
    required this.ligneNom,
    required this.dateHeure,
    required this.placesRestantes,
  });

  factory DepartOption.fromJson(Map<String, dynamic> json) => DepartOption(
        id: json['id'] as int,
        ligneNom: json['ligneNom'] as String,
        dateHeure: DateTime.parse(json['dateHeure'] as String),
        placesRestantes: json['placesRestantes'] as int,
      );

  final int id;
  final String ligneNom;
  final DateTime dateHeure;

  /// Au moment de la dernière lecture : peut être périmé hors ligne.
  final int placesRestantes;

  Map<String, dynamic> toJson() => {
        'id': id,
        'ligneNom': ligneNom,
        'dateHeure': dateHeure.toUtc().toIso8601String(),
        'placesRestantes': placesRestantes,
      };
}

class DepartRepository {
  DepartRepository({required this.api, required this.cache});

  final ApiClient api;
  final CacheStore cache;

  static String _cacheKey(int userId) => 'u$userId:departs_a_vendre';

  /// Départs non terminés, du plus proche au plus lointain. Utilisable hors ligne.
  Future<Loaded<List<DepartOption>>> loadSellable(AppUser user) async {
    try {
      final options = await _fetch();
      await cache.put(_cacheKey(user.id), options.map((o) => o.toJson()).toList());
      return Loaded(options);
    } on NetworkException {
      final cached = cache.get(_cacheKey(user.id));
      if (cached == null) throw const NoCachedDataException();
      final options = (cached.data as List)
          .map((o) => DepartOption.fromJson(Map<String, dynamic>.from(o as Map)))
          .toList();
      return Loaded(options, fromCache: true, savedAt: cached.savedAt);
    }
  }

  Future<List<DepartOption>> _fetch() async {
    final responses = await Future.wait([api.get('/departs/'), api.get('/lignes/')]);
    final lignes = {
      for (final l in (responses[1] as List).cast<Map<String, dynamic>>())
        l['id'] as int: l['nom'] as String,
    };
    final options = (responses[0] as List)
        .cast<Map<String, dynamic>>()
        .where((d) => d['statut'] != 'termine')
        .map((d) => DepartOption(
              id: d['id'] as int,
              ligneNom: lignes[d['ligne']] ?? 'Ligne ${d['ligne']}',
              dateHeure: DateTime.parse(d['date_heure'] as String),
              placesRestantes: d['places_restantes'] as int,
            ))
        .toList()
      ..sort((a, b) => a.dateHeure.compareTo(b.dateHeure));
    return options;
  }
}
