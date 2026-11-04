import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useActions from '../api/useActions.js'
import useChargement from '../api/useChargement.js'
import Alert from '../components/Alert.jsx'
import Badge from '../components/Badge.jsx'
import Layout from '../components/Layout.jsx'
import { formatDuree, formatFCFA } from '../lib/format.js'

const VIDE = { nom: '', gare_depart: '', gare_arrivee: '', tarif: '', distance_km: '', heures: '', minutes: '' }

function valeursDe(ligne) {
  if (!ligne) return VIDE
  const duree = ligne.duree_prevue_minutes
  return {
    nom: ligne.nom,
    gare_depart: String(ligne.gare_depart),
    gare_arrivee: String(ligne.gare_arrivee),
    tarif: ligne.tarif === null ? '' : String(Number(ligne.tarif)),
    distance_km: ligne.distance_km ?? '',
    heures: duree ? String(Math.floor(duree / 60)) : '',
    minutes: duree ? String(duree % 60) : '',
  }
}

/** Le formulaire d'une ligne (`ligne` absente : une nouvelle ligne). */
function FicheLigne({ ligne, gares, onEnregistre, onSupprime }) {
  const [valeurs, setValeurs] = useState(() => valeursDe(ligne))
  const { agir, envoi, message } = useActions(onEnregistre)
  const changer = (champ) => (event) => setValeurs({ ...valeurs, [champ]: event.target.value })
  const nomDe = (id) => gares.find((g) => String(g.id) === id)?.nom

  function choisirGare(champ) {
    return (event) => {
      const suivantes = { ...valeurs, [champ]: event.target.value }
      // Une nouvelle ligne prend le nom de son trajet tant qu'on ne lui en a pas donné un autre.
      const propose = (v) => (v.gare_depart && v.gare_arrivee ? `${nomDe(v.gare_depart)} – ${nomDe(v.gare_arrivee)}` : '')
      if (!ligne && (!valeurs.nom || valeurs.nom === propose(valeurs))) suivantes.nom = propose(suivantes)
      setValeurs(suivantes)
    }
  }

  async function supprimer() {
    // Un élément déjà utilisé (départs, tickets, historique) se garde : le serveur refuse et dit pourquoi.
    if (!window.confirm(`Supprimer la ligne « ${ligne.nom} » ?`)) return
    await agir(() => apiFetch(`/lignes/${ligne.id}/`, { method: 'DELETE' }).then(() => onSupprime()), null)
  }

  async function enregistrer(event) {
    event.preventDefault()
    const minutes = (Number(valeurs.heures) || 0) * 60 + (Number(valeurs.minutes) || 0)
    const corps = {
      nom: valeurs.nom,
      gare_depart: Number(valeurs.gare_depart),
      gare_arrivee: Number(valeurs.gare_arrivee),
      tarif: valeurs.tarif === '' ? null : valeurs.tarif,
      distance_km: valeurs.distance_km === '' ? null : Number(valeurs.distance_km),
      duree_prevue_minutes: minutes || null,
    }
    const ok = await agir(
      ligne
        ? () => apiFetch(`/lignes/${ligne.id}/`, { method: 'PATCH', body: corps })
        : () => apiFetch('/lignes/', { method: 'POST', body: corps }),
      ligne ? `Ligne « ${valeurs.nom} » enregistrée.` : `Ligne « ${valeurs.nom} » créée.`,
    )
    if (ok && !ligne) setValeurs(VIDE)
  }

  return (
    <form onSubmit={enregistrer}>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      <div className="form-grid">
        <label>
          Gare de départ
          <select value={valeurs.gare_depart} onChange={choisirGare('gare_depart')} required>
            <option value="">— Choisir —</option>
            {gares.map((g) => (
              <option key={g.id} value={g.id}>
                {g.nom}
              </option>
            ))}
          </select>
        </label>
        <label>
          Gare d&apos;arrivée
          <select value={valeurs.gare_arrivee} onChange={choisirGare('gare_arrivee')} required>
            <option value="">— Choisir —</option>
            {gares.map((g) => (
              <option key={g.id} value={g.id}>
                {g.nom}
              </option>
            ))}
          </select>
        </label>
        <label>
          Nom de la ligne
          <input value={valeurs.nom} onChange={changer('nom')} maxLength={255} required />
        </label>
        <label>
          Tarif (FCFA)
          <input type="number" min="1" step="any" value={valeurs.tarif} onChange={changer('tarif')} placeholder="vide = prix saisi à la vente" />
        </label>
        <label>
          Distance (km)
          <input type="number" min="1" step="1" value={valeurs.distance_km} onChange={changer('distance_km')} />
        </label>
        <label>
          Durée prévue (heures)
          <input type="number" min="0" step="1" value={valeurs.heures} onChange={changer('heures')} />
        </label>
        <label>
          (minutes)
          <input type="number" min="0" max="59" step="1" value={valeurs.minutes} onChange={changer('minutes')} />
        </label>
      </div>
      {ligne && valeurs.tarif !== valeursDe(ligne).tarif && (
        <p className="muted">Le nouveau tarif s&apos;appliquera aux prochaines ventes ; les billets déjà vendus gardent leur prix.</p>
      )}
      <div className="fiche-actions">
        <button type="submit" disabled={envoi}>
          {ligne ? 'Enregistrer la ligne' : 'Créer la ligne'}
        </button>
        {ligne && onSupprime && (
          <button type="button" className="button-secondary" disabled={envoi} onClick={supprimer}>
            Supprimer la ligne
          </button>
        )}
      </div>
    </form>
  )
}

/**
 * Les lignes de la compagnie et leur tarif, tenus sans l'administration : créer une ligne, fixer ou changer son tarif (imposé à
 * la vente ; vide, le prix reste saisi au guichet), sa distance et sa durée prévue. La fermeture d'une ligne passe par sa demande
 * (tableau de bord), pas par ici ; une ligne ne se supprime pas : ses départs et ses billets y restent rattachés.
 */
export default function LignesPage() {
  const [ouverte, setOuverte] = useState(null)
  const { data, error, loading, recharger } = useChargement(async () => {
    const [lignes, gares] = await Promise.all([apiFetch('/lignes/'), apiFetch('/gares/')])
    return { lignes, gares }
  })

  if (!data) {
    return (
      <Layout title="Lignes et tarifs">
        <Alert>{error}</Alert>
        {loading && <p>Chargement…</p>}
      </Layout>
    )
  }

  const { lignes, gares } = data
  const ligne = lignes.find((l) => l.id === ouverte) || null

  return (
    <Layout title="Lignes et tarifs">
      <Alert>{error}</Alert>
      <section className="card">
        <h2>Lignes ({lignes.length})</h2>
        {lignes.length === 0 ? (
          <p className="muted">Aucune ligne : créez la première ci-dessous.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Ligne</th>
                  <th>Tarif</th>
                  <th>Distance</th>
                  <th>Durée prévue</th>
                  <th>État</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {lignes.map((l) => (
                  <tr key={l.id}>
                    <td>
                      {l.nom}
                      <div className="muted">
                        {l.gare_depart_nom} → {l.gare_arrivee_nom}
                      </div>
                    </td>
                    <td className="montant">{l.tarif === null ? <span className="muted">Prix libre</span> : formatFCFA(l.tarif)}</td>
                    <td>{l.distance_km ? `${l.distance_km.toLocaleString('fr-FR')} km` : '—'}</td>
                    <td>{formatDuree(l.duree_prevue_minutes)}</td>
                    <td>{l.est_fermee ? <Badge ton="rouge">Fermée</Badge> : <Badge ton="vert">Ouverte</Badge>}</td>
                    <td>
                      <button
                        type="button"
                        className="button-secondary button-small"
                        onClick={() => setOuverte(ouverte === l.id ? null : l.id)}
                      >
                        {ouverte === l.id ? 'Masquer' : 'Modifier'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {ligne && (
        <section className="card card-highlight">
          <h2>Ligne {ligne.nom}</h2>
          <FicheLigne key={ligne.id} ligne={ligne} gares={gares} onEnregistre={recharger} onSupprime={() => setOuverte(null)} />
        </section>
      )}

      <section className="card">
        <h2>Nouvelle ligne</h2>
        {gares.length < 2 ? (
          <p className="muted">Il faut au moins deux gares pour créer une ligne.</p>
        ) : (
          <FicheLigne key="nouvelle" gares={gares} onEnregistre={recharger} />
        )}
      </section>
    </Layout>
  )
}
