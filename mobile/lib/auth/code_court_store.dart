import 'dart:convert';
import 'dart:math';

import 'package:crypto/crypto.dart';

import '../storage/encryption_key.dart';

/// Le code court de l'agent, gardé dans le coffre du système : jamais le code lui-même, seulement son empreinte salée, avec le
/// compte auquel il appartient et le nombre d'erreurs (qui survit à la fermeture de l'application).
class CodeCourtStore {
  CodeCourtStore(this._secrets, {Random? random}) : _random = random ?? Random.secure();

  static const _cle = 'code_court';
  static const _tours = 10000;

  final SecretStore _secrets;
  final Random _random;

  Future<Map<String, dynamic>?> _lire() async {
    final brut = await _secrets.read(_cle);
    if (brut == null) return null;
    try {
      return jsonDecode(brut) as Map<String, dynamic>;
    } on Object {
      return null; // entrée illisible : comme s'il n'y avait pas de code
    }
  }

  Future<void> _ecrire(Map<String, dynamic> valeur) => _secrets.write(_cle, jsonEncode(valeur));

  Future<bool> existe() async => await _lire() != null;

  /// Le compte à qui appartient le code (un autre agent qui se connecte sur ce téléphone l'efface).
  Future<int?> proprietaire() async => (await _lire())?['utilisateur'] as int?;

  Future<int> echecs() async => (await _lire())?['echecs'] as int? ?? 0;

  Future<void> definir(int utilisateur, String code) async {
    final sel = List<int>.generate(16, (_) => _random.nextInt(256));
    await _ecrire({
      'utilisateur': utilisateur,
      'sel': base64Url.encode(sel),
      'empreinte': base64Url.encode(_empreinte(code, sel)),
      'echecs': 0,
    });
  }

  /// Vrai si le code est le bon (le compteur d'erreurs repart alors de zéro) ; faux sinon, erreur comptée.
  Future<bool> verifier(String code) async {
    final valeur = await _lire();
    if (valeur == null) return false;
    final attendue = base64Url.decode(valeur['empreinte'] as String);
    final obtenue = _empreinte(code, base64Url.decode(valeur['sel'] as String));
    final bon = _egales(attendue, obtenue);
    await _ecrire({...valeur, 'echecs': bon ? 0 : (valeur['echecs'] as int? ?? 0) + 1});
    return bon;
  }

  Future<void> effacer() => _secrets.delete(_cle);

  static List<int> _empreinte(String code, List<int> sel) {
    var bloc = Hmac(sha256, sel).convert(utf8.encode(code)).bytes;
    for (var i = 0; i < _tours; i++) {
      bloc = sha256.convert([...bloc, ...sel]).bytes;
    }
    return bloc;
  }

  // Comparaison en temps constant : la durée ne trahit pas le nombre d'octets justes.
  static bool _egales(List<int> a, List<int> b) {
    if (a.length != b.length) return false;
    var difference = 0;
    for (var i = 0; i < a.length; i++) {
      difference |= a[i] ^ b[i];
    }
    return difference == 0;
  }
}
