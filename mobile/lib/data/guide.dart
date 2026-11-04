import '../api/api_client.dart';
import '../api/api_exception.dart';
import '../auth/app_user.dart';
import '../storage/cache_store.dart';
import 'loaded.dart';

/// Un écran cité par une fiche : page du site ou écran du téléphone.
class GuideEcran {
  const GuideEcran({required this.titre, required this.usage, required this.mobile});

  factory GuideEcran.fromJson(Map<String, dynamic> json) => GuideEcran(
        titre: json['titre'] as String,
        usage: json['usage'] as String,
        mobile: json['support'] == 'mobile',
      );

  final String titre;
  final String usage;
  final bool mobile;
}

/// Un geste pas à pas, son moment de la journée, les postes avec qui il se coordonne et, s'il dépend du règlement intérieur,
/// si la compagnie le permet.
class GuideTache {
  const GuideTache({
    required this.titre,
    required this.etapes,
    required this.moment,
    required this.avec,
    this.permise,
  });

  factory GuideTache.fromJson(Map<String, dynamic> json) => GuideTache(
        titre: json['titre'] as String,
        etapes: (json['etapes'] as List).cast<String>(),
        moment: json['moment'] as String,
        avec: {
          for (final poste in (json['avec'] as List? ?? const []).cast<Map<String, dynamic>>())
            poste['poste'] as String: poste['libelle'] as String,
        },
        permise: json['permise'] as bool?,
      );

  final String titre;
  final List<String> etapes;
  final String moment;

  /// Poste → libellé.
  final Map<String, String> avec;
  final bool? permise;
}

/// Une règle du règlement intérieur qui vise le poste, telle que la compagnie du lecteur l'a réglée.
class GuideRegle {
  const GuideRegle({required this.libelle, required this.permis, required this.decide});

  factory GuideRegle.fromJson(Map<String, dynamic> json) => GuideRegle(
        libelle: json['libelle'] as String,
        permis: json['permis'] as bool,
        decide: json['decide'] as String,
      );

  final String libelle;
  final bool permis;
  final String decide;
}

class GuideFiche {
  const GuideFiche({
    required this.poste,
    required this.libelle,
    required this.mission,
    required this.ecrans,
    required this.taches,
    required this.contacts,
    required this.astuces,
    this.reglePar = const [],
    this.regle = const [],
    this.reglement = const [],
  });

  factory GuideFiche.fromJson(Map<String, dynamic> json) => GuideFiche(
        poste: json['poste'] as String? ?? '',
        libelle: json['libelle'] as String? ?? 'Pour tous les postes',
        mission: json['mission'] as String? ?? '',
        ecrans: _liste(json['ecrans'], GuideEcran.fromJson),
        taches: _liste(json['taches'], GuideTache.fromJson),
        contacts: (json['contacts'] as List? ?? const []).cast<String>(),
        astuces: (json['astuces'] as List? ?? const []).cast<String>(),
        reglePar: (json['regle_par'] as List? ?? const []).cast<String>(),
        regle: (json['regle'] as List? ?? const []).cast<String>(),
        reglement: _liste(json['reglement'], GuideRegle.fromJson),
      );

  final String poste;
  final String libelle;
  final String mission;
  final List<GuideEcran> ecrans;
  final List<GuideTache> taches;
  final List<String> contacts;
  final List<String> astuces;
  final List<String> reglePar;
  final List<String> regle;
  final List<GuideRegle> reglement;
}

class GuidePole {
  const GuidePole({required this.code, required this.libelle, required this.fiches});

  factory GuidePole.fromJson(Map<String, dynamic> json) => GuidePole(
        code: json['pole'] as String,
        libelle: json['libelle'] as String,
        fiches: _liste(json['postes'], GuideFiche.fromJson),
      );

  final String code;
  final String libelle;
  final List<GuideFiche> fiches;
}

/// Le guide d'utilisation (`/guides/`) : la fiche de chaque poste, rangée par pôle, et ce qui vaut pour tous.
class Guide {
  const Guide({required this.monPoste, required this.monPole, required this.moments, required this.communs, required this.poles});

  factory Guide.fromJson(Map<String, dynamic> json) => Guide(
        monPoste: json['mon_poste'] as String?,
        monPole: json['mon_pole'] as String?,
        moments: {
          for (final moment in (json['moments'] as List).cast<Map<String, dynamic>>())
            moment['code'] as String: moment['libelle'] as String,
        },
        communs: GuideFiche.fromJson(Map<String, dynamic>.from(json['communs'] as Map)),
        poles: _liste(json['poles'], GuidePole.fromJson),
      );

  final String? monPoste;
  final String? monPole;

  /// Les moments de la journée, dans leur ordre (code → libellé).
  final Map<String, String> moments;
  final GuideFiche communs;
  final List<GuidePole> poles;

  GuidePole poleDe(String poste) => poles.firstWhere((pole) => pole.fiches.any((fiche) => fiche.poste == poste));

  GuideFiche fiche(String poste) => poleDe(poste).fiches.firstWhere((fiche) => fiche.poste == poste);

  /// La fiche qui s'ouvre d'abord : celle du lecteur, sinon la première.
  String get posteInitial {
    final postes = [for (final pole in poles) for (final fiche in pole.fiches) fiche.poste];
    return postes.contains(monPoste) ? monPoste! : postes.first;
  }
}

List<T> _liste<T>(Object? brut, T Function(Map<String, dynamic>) lire) =>
    [for (final element in (brut as List? ?? const [])) lire(Map<String, dynamic>.from(element as Map))];

/// Lit le guide et le garde sur le téléphone, pour le relire hors ligne (le règlement intérieur qu'il cite est celui du jour où
/// il a été lu).
class GuideRepository {
  GuideRepository({required this.api, required this.cache});

  final ApiClient api;
  final CacheStore cache;

  static String _cle(int utilisateur) => 'u$utilisateur:guide';

  /// Lève [NoCachedDataException] si le réseau manque et que le guide n'a jamais été lu sur ce téléphone.
  Future<Loaded<Guide>> charger(AppUser user) async {
    try {
      final brut = await api.get('/guides/') as Map<String, dynamic>;
      await cache.put(_cle(user.id), brut);
      return Loaded(Guide.fromJson(brut));
    } on NetworkException {
      final garde = cache.get(_cle(user.id));
      if (garde == null) throw const NoCachedDataException();
      return Loaded(
        Guide.fromJson(Map<String, dynamic>.from(garde.data! as Map)),
        fromCache: true,
        savedAt: garde.savedAt,
      );
    }
  }
}
