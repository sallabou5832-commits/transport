import 'dart:math';

enum ActionStatus {
  /// À envoyer (ou à renvoyer) au serveur.
  pending,

  /// Refusée par le serveur (erreur métier) : à revoir par l'utilisateur.
  rejected,
}

const _unset = Object();

/// Une action faite par l'utilisateur, stockée sur l'appareil jusqu'à son envoi.
class PendingAction {
  const PendingAction({
    required this.id,
    required this.userId,
    required this.type,
    required this.payload,
    required this.createdAt,
    this.attempts = 0,
    this.status = ActionStatus.pending,
    this.lastError,
  });

  factory PendingAction.create({
    required int userId,
    required String type,
    required Map<String, dynamic> payload,
    DateTime? now,
  }) =>
      PendingAction(
        id: newActionId(),
        userId: userId,
        type: type,
        payload: payload,
        createdAt: (now ?? DateTime.now()).toUtc(),
      );

  factory PendingAction.fromJson(Map<String, dynamic> json) => PendingAction(
        id: json['id'] as String,
        userId: json['userId'] as int,
        type: json['type'] as String,
        payload: Map<String, dynamic>.from(json['payload'] as Map),
        createdAt: DateTime.parse(json['createdAt'] as String),
        attempts: json['attempts'] as int? ?? 0,
        status: ActionStatus.values.byName(json['status'] as String? ?? 'pending'),
        lastError: json['lastError'] as String?,
      );

  /// Identifiant unique généré sur l'appareil ; envoyé comme `Idempotency-Key`.
  final String id;

  /// Propriétaire de l'action : elle n'est jamais envoyée avec le compte d'un autre.
  final int userId;

  /// Nature de l'action (voir `ActionTypes`) : sert à choisir l'appel API à faire.
  final String type;
  final Map<String, dynamic> payload;
  final DateTime createdAt;
  final int attempts;
  final ActionStatus status;
  final String? lastError;

  PendingAction copyWith({int? attempts, ActionStatus? status, Object? lastError = _unset}) =>
      PendingAction(
        id: id,
        userId: userId,
        type: type,
        payload: payload,
        createdAt: createdAt,
        attempts: attempts ?? this.attempts,
        status: status ?? this.status,
        lastError: identical(lastError, _unset) ? this.lastError : lastError as String?,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'userId': userId,
        'type': type,
        'payload': payload,
        'createdAt': createdAt.toIso8601String(),
        'attempts': attempts,
        'status': status.name,
        'lastError': lastError,
      };
}

/// UUID v4 aléatoire, sans dépendance externe.
String newActionId([Random? random]) {
  final rng = random ?? Random.secure();
  final bytes = List<int>.generate(16, (_) => rng.nextInt(256));
  bytes[6] = (bytes[6] & 0x0f) | 0x40; // version 4
  bytes[8] = (bytes[8] & 0x3f) | 0x80; // variante RFC 4122
  final hex = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-'
      '${hex.substring(16, 20)}-${hex.substring(20)}';
}
