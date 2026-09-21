import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../api/client.js'
import { ROLE_LABELS } from '../auth/roles.js'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'
import Badge from '../components/Badge.jsx'
import { formatDateHeure } from '../lib/format.js'

const TAILLE_PAGE = 50
const FILTRES_VIDES = { objet_type: '', action: '', date_debut: '', date_fin: '' }

const TYPES = {
  'billetterie.ticket': 'Ticket',
  'billetterie.depart': 'Départ',
  'personnel_roulant.feuillederoute': 'Feuille de route',
  'personnel_roulant.checklistdepart': 'Checklist',
  'personnel_roulant.incident': 'Incident',
  'maintenance.ordrereparation': 'Ordre de réparation',
  'maintenance.sortiepiece': 'Sortie de pièce',
  'maintenance.piece': 'Pièce',
  'reseau.vehicule': 'Véhicule',
  'reseau.gare': 'Gare',
  'reseau.ligne': 'Ligne',
  'supports.dossieragent': 'Dossier RH',
  'supports.assurance': 'Assurance',
  'supports.sinistre': 'Sinistre',
  'core.user': 'Compte',
  'core.company': 'Compagnie',
}

const ACTIONS = {
  creation: ['Création', 'vert'],
  modification: ['Modification', 'bleu'],
  suppression: ['Suppression', 'rouge'],
  annulation: ['Annulation', 'orange'],
  connexion: ['Connexion', 'neutre'],
  connexion_echec: ['Échec de connexion', 'rouge'],
}

const MAX_CHAMPS_AFFICHES = 6

function texte(valeur) {
  if (valeur === null || valeur === undefined || valeur === '') return '∅'
  return String(valeur)
}

/** Ce qui a changé, lisible : « champ : avant → après » pour une modification, l'état pour une création. */
function DetailChangements({ entree }) {
  const paires = Object.entries(entree.changements || {})
  if (paires.length === 0) return <span className="muted">—</span>
  return (
    <ul className="stat-list">
      {paires.slice(0, MAX_CHAMPS_AFFICHES).map(([champ, valeur]) => (
        <li key={champ}>
          <span>{champ}</span>
          <span>
            {Array.isArray(valeur) ? `${texte(valeur[0])} → ${texte(valeur[1])}` : texte(valeur)}
          </span>
        </li>
      ))}
      {paires.length > MAX_CHAMPS_AFFICHES && (
        <li className="muted">… et {paires.length - MAX_CHAMPS_AFFICHES} autre(s) champ(s)</li>
      )}
    </ul>
  )
}

export default function AuditPage() {
  const [filtres, setFiltres] = useState(FILTRES_VIDES)
  const [entrees, setEntrees] = useState([])
  const [total, setTotal] = useState(0)
  const [erreur, setErreur] = useState('')
  const [chargement, setChargement] = useState(true)

  const charger = useCallback(async (decalage, filtresActifs) => {
    setChargement(true)
    setErreur('')
    try {
      const parametres = new URLSearchParams({ limit: String(TAILLE_PAGE), offset: String(decalage) })
      Object.entries(filtresActifs).forEach(([cle, valeur]) => valeur && parametres.set(cle, valeur))
      const page = await apiFetch(`/audit/?${parametres}`)
      setEntrees((precedentes) => (decalage === 0 ? page.results : [...precedentes, ...page.results]))
      setTotal(page.count)
    } catch (err) {
      setErreur(err.message)
    } finally {
      setChargement(false)
    }
  }, [])

  // Premier chargement : aucune mise à jour d'état avant la réponse (les suivants passent par `charger`).
  useEffect(() => {
    let annule = false
    apiFetch(`/audit/?limit=${TAILLE_PAGE}&offset=0`)
      .then((page) => {
        if (annule) return
        setEntrees(page.results)
        setTotal(page.count)
      })
      .catch((err) => {
        if (!annule) setErreur(err.message)
      })
      .finally(() => {
        if (!annule) setChargement(false)
      })
    return () => {
      annule = true
    }
  }, [])

  function rechercher(event) {
    event.preventDefault()
    charger(0, filtres)
  }

  return (
    <Layout title="Journal d'audit">
      <p className="muted">
        Qui a fait quoi, quand et d’où : chaque création, modification, suppression et connexion est enregistrée, du plus
        récent au plus ancien. Le journal ne se modifie ni ne se supprime.
      </p>

      <form className="toolbar" onSubmit={rechercher}>
        <label>
          Type d’objet
          <select value={filtres.objet_type} onChange={(e) => setFiltres({ ...filtres, objet_type: e.target.value })}>
            <option value="">Tous</option>
            {Object.entries(TYPES).map(([valeur, label]) => (
              <option key={valeur} value={valeur}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Action
          <select value={filtres.action} onChange={(e) => setFiltres({ ...filtres, action: e.target.value })}>
            <option value="">Toutes</option>
            {Object.entries(ACTIONS).map(([valeur, [label]]) => (
              <option key={valeur} value={valeur}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Du
          <input type="date" value={filtres.date_debut} onChange={(e) => setFiltres({ ...filtres, date_debut: e.target.value })} />
        </label>
        <label>
          Au
          <input type="date" value={filtres.date_fin} onChange={(e) => setFiltres({ ...filtres, date_fin: e.target.value })} />
        </label>
        <button type="submit" disabled={chargement}>
          Rechercher
        </button>
      </form>

      <Alert>{erreur}</Alert>
      {!chargement && !erreur && entrees.length === 0 && <p>Aucune entrée pour ces critères.</p>}

      {entrees.length > 0 && (
        <>
          <p className="muted">
            {entrees.length} entrée(s) affichée(s) sur {total}.
          </p>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Acteur</th>
                  <th>Action</th>
                  <th>Objet</th>
                  <th>Changements</th>
                  <th>Adresse</th>
                </tr>
              </thead>
              <tbody>
                {entrees.map((entree) => {
                  const [libelle, ton] = ACTIONS[entree.action] || [entree.action, 'neutre']
                  return (
                    <tr key={entree.id}>
                      <td>{formatDateHeure(entree.date)}</td>
                      <td>
                        {entree.acteur_nom || 'système'}
                        <br />
                        <span className="muted">{ROLE_LABELS[entree.acteur_role] || entree.acteur_role}</span>
                      </td>
                      <td>
                        <Badge ton={ton}>{libelle}</Badge>
                      </td>
                      <td>
                        {TYPES[entree.objet_type] || entree.objet_type}
                        <br />
                        <span className="muted">{entree.objet_repr}</span>
                      </td>
                      <td>
                        <DetailChangements entree={entree} />
                      </td>
                      <td>{entree.adresse_ip || '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          {entrees.length < total && (
            <button type="button" className="button-secondary" disabled={chargement} onClick={() => charger(entrees.length, filtres)}>
              {chargement ? 'Chargement…' : 'Charger plus'}
            </button>
          )}
        </>
      )}
    </Layout>
  )
}
