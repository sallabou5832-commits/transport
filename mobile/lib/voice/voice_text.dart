/// Compréhension et mise en forme du texte pour la commande vocale (français).
///
/// Tout ce fichier est fait de fonctions pures : aucune dépendance à un moteur de
/// reconnaissance ou de synthèse vocale, aucun accès réseau. C'est ce qui les rend
/// testables sans microphone (voir `test/voice_text_test.dart`) — la reconnaissance
/// elle-même dépend du service du téléphone et n'est pas testée ici.
library;

/// Minuscules, accents retirés, espaces multiples réduits à un seul.
///
/// Rend la recherche de mots-clés fiable malgré les variantes de la dictée
/// (« Défaut », « defaut », « DÉFAUT »... doivent être reconnus pareil).
String normalizeSpoken(String text) {
  const accentuees = 'àâäáãåèéêëìíîïòóôöõùúûüçñ';
  const simples = 'aaaaaaeeeeiiiiooooouuuucn';
  final buffer = StringBuffer();
  for (final rune in text.trim().toLowerCase().runes) {
    final char = String.fromCharCode(rune);
    final index = accentuees.indexOf(char);
    buffer.write(index >= 0 ? simples[index] : char);
  }
  return buffer.toString().replaceAll(RegExp(r'\s+'), ' ').trim();
}

/// Vrai si le texte normalisé contient au moins un des mots-clés (en mot entier : « ok »
/// ne doit pas se déclencher sur « moto »).
bool _contientUnDe(String normalise, List<String> motsCles) =>
    motsCles.any((mot) => RegExp(r'\b' + RegExp.escape(mot) + r'\b').hasMatch(normalise));

/// Les mots d'une phrase normalisée ; l'apostrophe sépare (« n'est » donne « n », « est »).
List<String> _mots(String normalise) =>
    RegExp(r'[a-z0-9]+').allMatches(normalise).map((mot) => mot.group(0)!).toList();

/// Où apparaît chacun des mots-clés, en positions de mots [début, fin) ; un mot-clé peut
/// tenir en plusieurs mots (« à changer », « c'est bon »).
List<(int, int)> _occurrences(List<String> mots, List<String> motsCles) {
  final trouvees = <(int, int)>[];
  for (final cle in motsCles) {
    final morceaux = cle.split(' ');
    for (var debut = 0; debut + morceaux.length <= mots.length; debut++) {
      var egal = true;
      for (var i = 0; i < morceaux.length && egal; i++) {
        egal = mots[debut + i] == morceaux[i];
      }
      if (egal) trouvees.add((debut, debut + morceaux.length));
    }
  }
  return trouvees;
}

/// Ce qui nie le mot qui suit (« pas bon », « aucun problème », « sans défaut ») ; à l'oral
/// le « ne » tombe souvent, « pas » suffit.
const _negationsAvant = {'pas', 'plus', 'jamais', 'aucun', 'aucune', 'sans', 'ni', 'non', 'ne', 'n'};

/// Ce qui nie le verbe qui précède, à l'oral (« je valide pas », « confirme jamais »).
const _negationsApres = {'pas', 'plus', 'jamais'};

/// Vrai si une négation précède ce mot-clé de trois mots au plus (« pas très bon »), sans
/// remonter au-delà du mot-clé précédent : dans « pas de problème, ok », le « pas » nie
/// « problème », pas « ok ».
bool _nieAvant(List<String> mots, (int, int) occurrence, List<(int, int)> toutes) {
  var borne = occurrence.$1 - 3;
  for (final autre in toutes) {
    if (autre.$2 <= occurrence.$1 && autre.$2 > borne) borne = autre.$2;
  }
  for (var i = occurrence.$1 - 1; i >= 0 && i >= borne; i--) {
    if (_negationsAvant.contains(mots[i])) return true;
  }
  return false;
}

/// Vrai si une négation suit ce verbe de deux mots au plus, sans dépasser le mot-clé suivant.
bool _nieApres(List<String> mots, (int, int) occurrence, List<(int, int)> toutes) {
  var borne = occurrence.$2 + 2;
  for (final autre in toutes) {
    if (autre.$1 >= occurrence.$2 && autre.$1 < borne) borne = autre.$1;
  }
  for (var i = occurrence.$2; i < mots.length && i < borne; i++) {
    if (_negationsApres.contains(mots[i])) return true;
  }
  return false;
}

/// Met une majuscule à chaque mot (un nom dicté arrive tout en minuscules, contrairement
/// à la saisie au clavier qui capitalise déjà au fil de la frappe).
String capitalizeWords(String text) => text
    .trim()
    .split(RegExp(r'\s+'))
    .where((mot) => mot.isNotEmpty)
    .map((mot) => mot[0].toUpperCase() + mot.substring(1).toLowerCase())
    .join(' ');

/// Garde uniquement les chiffres (numéro de téléphone dicté : les espaces et tirets
/// éventuels de la dictée n'ont pas de sens à conserver).
String extractDigitsOnly(String text) => text.replaceAll(RegExp(r'[^0-9]'), '');

/// Premier nombre dicté (prix...), avec une décimale éventuelle dite « virgule » ou
/// « point ». Les moteurs de reconnaissance français convertissent déjà en général les
/// nombres prononcés en chiffres : on ne réanalyse pas les nombres écrits en toutes
/// lettres. Renvoie `null` si aucun chiffre n'est reconnu.
String? extractNumber(String text) {
  final prepare = text
      .replaceAll(RegExp(r'\s*\b(?:virgule|point)\b\s*', caseSensitive: false), '.')
      .replaceAll(',', '.');
  return RegExp(r'\d+(?:\.\d+)?').firstMatch(prepare)?.group(0);
}

/// Mode de paiement compris dans une phrase dictée (`'especes'` ou `'mobile_money'`,
/// les mêmes valeurs que le formulaire tactile), ou `null` si rien n'est reconnu.
String? parseModePaiement(String text) {
  final normalise = normalizeSpoken(text);
  if (_contientUnDe(normalise, const ['mobile money', 'mobile', 'orange money', 'wave', 'mtn money', 'free money'])) {
    return 'mobile_money';
  }
  if (_contientUnDe(normalise, const ['espece', 'especes', 'liquide', 'cash'])) {
    return 'especes';
  }
  return null;
}

const _motsDefaut = [
  'defaut', 'defauts', 'probleme', 'problemes', 'panne', 'pannes', 'mauvais', 'mauvaise', 'mauvaises',
  'use', 'uses', 'usee', 'usees', 'casse', 'casses', 'cassee', 'cassees', 'a changer', 'hs',
];
const _motsAccord = [
  'ok', 'bon', 'bons', 'bonne', 'bonnes', 'correct', 'corrects', 'correcte', 'correctes',
  'oui', 'ras', 'rien a signaler', 'nickel', 'impeccable',
];

/// État d'un item de checklist compris dans une phrase dictée (`'ok'` ou `'defaut'`,
/// les mêmes valeurs que `EtatChecklist` côté serveur), ou `null` si incompris.
///
/// La sécurité passe avant la commodité : un défaut dit, ou un accord nié (« pas bon »,
/// « c'est pas ok »), donne un défaut. Un défaut nié seul (« pas de défaut », « aucun
/// problème ») ne vaut pas « OK » : dans le doute, rien n'est renvoyé et l'agent reprend
/// au clavier.
String? parseEtatChecklist(String text) {
  final mots = _mots(normalizeSpoken(text));
  final defauts = _occurrences(mots, _motsDefaut);
  final accords = _occurrences(mots, _motsAccord);
  final toutes = [...defauts, ...accords];
  bool nie((int, int) occurrence) => _nieAvant(mots, occurrence, toutes);
  if (defauts.any((occurrence) => !nie(occurrence)) || accords.any(nie)) return 'defaut';
  if (accords.isNotEmpty) return 'ok';
  return null;
}

/// Ce que l'utilisateur veut faire de la confirmation orale : valider ce qui a été
/// compris, ou reprendre à la main (corriger au clavier).
enum VoiceIntent {
  /// « confirmer », « valider »... : enregistrer ce qui a été dicté.
  confirmer,

  /// « modifier », « annuler »... : l'utilisateur préfère corriger lui-même.
  modifier,

  /// Rien de reconnu : par prudence, on ne valide jamais dans le doute — même
  /// traitement que « modifier » (retour à la saisie tactile).
  inconnu,
}

/// Une confirmation niée (« je valide pas », « ne confirme pas ») n'est jamais une
/// confirmation : c'est un refus. Confirmer et refuser dans la même phrase : inconnu.
VoiceIntent parseConfirmationIntent(String text) {
  final mots = _mots(normalizeSpoken(text));
  final confirmations = _occurrences(mots, const ['confirme', 'confirmer', 'valide', 'valider', 'envoie', 'envoyer', 'c est bon']);
  final modifications = _occurrences(
    mots,
    const ['modifie', 'modifier', 'recommence', 'recommencer', 'annule', 'annuler', 'corrige', 'corriger'],
  );
  final toutes = [...confirmations, ...modifications];
  bool nie((int, int) occurrence) => _nieAvant(mots, occurrence, toutes) || _nieApres(mots, occurrence, toutes);
  final confirme = confirmations.any((occurrence) => !nie(occurrence));
  final refuse = confirmations.any(nie) || modifications.any((occurrence) => !nie(occurrence));
  if (confirme && !refuse) return VoiceIntent.confirmer;
  if (refuse && !confirme) return VoiceIntent.modifier;
  return VoiceIntent.inconnu;
}

/// Message lu avant la validation finale de la vente d'un ticket : récapitule ce qui a
/// été compris pour que l'utilisateur puisse l'entendre avant que rien ne soit envoyé.
String recapVenteTicket({
  required String nom,
  required String telephone,
  required String prix,
  required String modePaiement,
}) {
  final modeLabel = modePaiement == 'mobile_money' ? 'mobile money' : 'espèces';
  final nomPhrase = nom.trim().isEmpty ? 'nom non renseigné' : nom.trim();
  final telPhrase = telephone.trim().isEmpty ? 'téléphone non renseigné' : telephone.trim();
  final prixPhrase = prix.trim().isEmpty ? 'prix non renseigné' : '${prix.trim()} francs C F A';
  return 'Vente d\'un ticket pour $nomPhrase, téléphone $telPhrase, $prixPhrase, payé en $modeLabel. '
      'Dites confirmer pour valider, ou modifier pour corriger vous-même.';
}

/// Message lu avant la validation finale de la checklist avant-départ : détaille l'état
/// de chaque item et signale les défauts, dans l'ordre où ils ont été demandés.
String recapChecklistDepart({
  required List<String> items,
  required Map<String, String> labels,
  required Map<String, String> etats,
  required Map<String, String> commentaires,
}) {
  final phrases = items.map((item) {
    final label = labels[item] ?? item;
    final enDefaut = etats[item] == 'defaut';
    final commentaire = enDefaut && (commentaires[item] ?? '').trim().isNotEmpty
        ? ' : ${commentaires[item]!.trim()}'
        : '';
    return '$label ${enDefaut ? 'en défaut' : 'OK'}$commentaire';
  }).join('. ');
  final defauts = items.where((item) => etats[item] == 'defaut').map((item) => labels[item] ?? item).toList();
  final alerte = defauts.isEmpty ? 'Aucun défaut.' : 'Attention, défaut signalé sur : ${defauts.join(', ')}.';
  return 'Checklist avant-départ. $phrases. $alerte '
      'Dites confirmer pour valider, ou modifier pour corriger vous-même.';
}
