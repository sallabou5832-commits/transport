import '../api/api_client.dart';
import 'pending_action.dart';

/// Envoie une action au serveur. Lève [ApiException] / [NetworkException] en cas d'échec.
typedef ActionHandler = Future<void> Function(PendingAction action);

/// Natures d'actions pouvant être faites hors ligne.
///
/// Pour en ajouter une : déclarer son type ici, puis l'associer à son appel API
/// dans [buildActionHandlers]. Le reste (stockage, ordre, reprise, erreurs) est
/// déjà géré par `SyncService`.
abstract final class ActionTypes {
  static const venteTicket = 'vente_ticket';
}

Map<String, ActionHandler> buildActionHandlers(ApiClient api) => {
      ActionTypes.venteTicket: (action) => api.post(
            '/tickets/',
            body: action.payload,
            // Identifiant stable de l'action : permet au serveur d'ignorer un doublon
            // lorsqu'il saura l'exploiter (voir mobile/README.md, « Doublons »).
            headers: {'Idempotency-Key': action.id},
          ),
    };
