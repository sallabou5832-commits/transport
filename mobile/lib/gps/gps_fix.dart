/// Un relevé GPS prêt à envoyer au serveur — mêmes champs que `PositionSerializer` côté API
/// (`transpt1/personnel_roulant/serializers.py`).
class GpsFix {
  const GpsFix({
    required this.latitude,
    required this.longitude,
    this.vitesseKmh,
    required this.releveLe,
  });

  final double latitude;
  final double longitude;
  final int? vitesseKmh;
  final DateTime releveLe;

  Map<String, dynamic> toJson() => {
        'latitude': latitude.toStringAsFixed(6),
        'longitude': longitude.toStringAsFixed(6),
        if (vitesseKmh != null) 'vitesse_kmh': vitesseKmh,
        'releve_le': releveLe.toUtc().toIso8601String(),
      };

  factory GpsFix.fromJson(Map<String, dynamic> json) => GpsFix(
        latitude: double.parse(json['latitude'].toString()),
        longitude: double.parse(json['longitude'].toString()),
        vitesseKmh: json['vitesse_kmh'] as int?,
        releveLe: DateTime.parse(json['releve_le'] as String),
      );
}
