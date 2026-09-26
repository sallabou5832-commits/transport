import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'
import Badge from '../components/Badge.jsx'
import { formatDateHeure } from '../lib/format.js'

/** Les notes de service adressées à mon poste, de la plus récente à la plus ancienne (elles arrivent aussi dans la cloche d'alertes). */
export default function NotesPage() {
  const { data: notes, error, loading } = useChargement(() => apiFetch('/notes-service/'), { intervalleMs: 120000 })

  return (
    <Layout title="Notes de service">
      <Alert>{error}</Alert>
      {!notes ? (
        loading && <p>Chargement…</p>
      ) : notes.length === 0 ? (
        <p>Aucune note de service ne concerne votre poste.</p>
      ) : (
        notes.map((note) => (
          <section key={note.id} className="card">
            <h2>
              {note.titre} {note.urgente && <Badge ton="orange">Urgente</Badge>}
            </h2>
            <p>{note.contenu}</p>
            <p className="muted">
              {note.auteur_nom} — {formatDateHeure(note.cree_le)}
            </p>
          </section>
        ))
      )}
    </Layout>
  )
}
