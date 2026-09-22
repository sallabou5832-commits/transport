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
  static const checklistDepart = 'checklist_depart';
}

Map<String, ActionHandler> buildActionHandlers(ApiClient api) => {
      ActionTypes.venteTicket: (action) => api.post(
            '/tickets/',
            body: action.payload,
            // Identifiant stable de l'action : permet au serveur d'ignorer un doublon
            // lorsqu'il saura l'exploiter (voir mobile/README.md, « Doublons »).
            headers: {'Idempotency-Key': action.id},
          ),
      // Un item de checklist par requête (l'API n'a pas d'envoi groupé). Sans danger à
      // renvoyer en entier après une coupure réseau : le serveur met à jour l'item déjà
      // reçu au lieu de le dupliquer (voir `ChecklistDepartViewSet.create` côté serveur).
      ActionTypes.checklistDepart: (action) async {
        final feuilleDeRoute = action.payload['feuille_de_route'];
        final items = (action.payload['items'] as List).cast<Map<String, dynamic>>();
        for (final item in items) {
          await api.post(
            '/checklists/',
            body: {
              'feuille_de_route': feuilleDeRoute,
              'item': item['item'],
              'etat': item['etat'],
              'commentaire': item['commentaire'],
            },
          );
        }
      },
    };
