import { useEffect, useState } from 'react'
import { apiFetch } from '../api/client.js'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'

export default function MagasinierDashboard() {
  const [pieces, setPieces] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    apiFetch('/pieces/')
      .then(setPieces)
      .catch((err) => setError(err.message))
  }, [])

  const enAlerte = pieces.filter((p) => p.en_alerte)

  return (
    <Layout title="Tableau de bord — Magasinier">
      <Alert>{error}</Alert>

      {enAlerte.length > 0 && (
        <Alert type="warning">
          {enAlerte.length} pièce(s) sous le seuil d'alerte : {enAlerte.map((p) => p.nom).join(', ')}
        </Alert>
      )}

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
          {pieces.map((piece) => (
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
