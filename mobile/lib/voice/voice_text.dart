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

/// État d'un item de checklist compris dans une phrase dictée (`'ok'` ou `'defaut'`,
/// les mêmes valeurs que `EtatChecklist` côté serveur), ou `null` si incompris.
///
/// Limite connue : la négation n'est pas comprise (« pas de défaut » serait pris pour
/// un défaut). Sans ambiguïté à traiter en premier lieu, la checklist ne demande qu'un
/// mot ; en cas de doute mieux vaut ne rien renvoyer et laisser la reprise manuelle.
String? parseEtatChecklist(String text) {
  final normalise = normalizeSpoken(text);
  if (_contientUnDe(normalise, const ['defaut', 'probleme', 'panne', 'mauvais', 'usee', 'use', 'casse', 'a changer', 'hs'])) {
    return 'defaut';
  }
  if (_contientUnDe(normalise, const ['ok', 'bon', 'correct', 'oui', 'ras', 'rien a signaler', 'nickel', 'impeccable'])) {
    return 'ok';
  }
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

VoiceIntent parseConfirmationIntent(String text) {
  final normalise = normalizeSpoken(text);
  if (_contientUnDe(normalise, const ['confirme', 'confirmer', 'valide', 'valider', 'envoie', 'envoyer', 'c est bon'])) {
    return VoiceIntent.confirmer;
  }
  if (_contientUnDe(normalise, const ['modifie', 'modifier', 'recommence', 'recommencer', 'annule', 'annuler', 'corrige', 'corriger'])) {
    return VoiceIntent.modifier;
  }
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
