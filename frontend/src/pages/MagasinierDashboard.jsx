import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'
import DemandesPiecesMagasin from '../components/DemandesPiecesMagasin.jsx'
import SuggestionsCommande from '../components/SuggestionsCommande.jsx'

export default function MagasinierDashboard() {
  const { data: pieces, error, recharger } = useChargement(() => apiFetch('/pieces/'), { intervalleMs: 60000 })

  const enAlerte = (pieces ?? []).filter((p) => p.en_alerte)

  return (
    <Layout title="Tableau de bord — Magasinier">
      <Alert>{error}</Alert>

      {enAlerte.length > 0 && (
        <Alert type="warning">
          {enAlerte.length} pièce(s) sous le seuil d'alerte : {enAlerte.map((p) => p.nom).join(', ')}
        </Alert>
      )}

      <DemandesPiecesMagasin onChange={recharger} />
      <SuggestionsCommande />

      <h2 className="section-title">Stock</h2>
      <table className="table">
        <thead>
          <tr>
            <th>Nom</th>
            <th>Référence</th>
            <th>Stock</th>
            <th>Seuil d'alerte</th>
            <th>Statut</th>
          </tr>
        </thead>
        <tbody>
          {(pieces ?? []).map((piece) => (
            <tr key={piece.id} className={piece.en_alerte ? 'row-alerte' : ''}>
              <td>{piece.nom}</td>
              <td>{piece.reference}</td>
              <td>{piece.quantite_stock}</td>
              <td>{piece.seuil_alerte}</td>
              <td>{piece.en_alerte ? 'Rupture proche' : 'OK'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Layout>
  )
}
