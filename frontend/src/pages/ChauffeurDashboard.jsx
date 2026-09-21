import { useEffect, useState } from 'react'
import { apiFetch } from '../api/client.js'
import { useAuth } from '../auth/AuthContext.jsx'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'
import { LABELS_GRAVITE, LABELS_TYPE_INCIDENT } from '../lib/format.js'

const ITEMS_CHECKLIST = ['pneus', 'freins', 'carburant', 'eclairage', 'direction', 'ceintures']
const INCIDENT_VIDE = { type_incident: 'panne', gravite: 'moyenne', description: '' }

function estAujourdhui(dateIso) {
  const date = new Date(dateIso)
  const now = new Date()
  return (
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  )
}

export default function ChauffeurDashboard() {
  const { user } = useAuth()
  const [feuilles, setFeuilles] = useState([])
  const [lignes, setLignes] = useState({})
  const [error, setError] = useState('')
  const [checklistOuverte, setChecklistOuverte] = useState(null)
  const [etats, setEtats] = useState(() => Object.fromEntries(ITEMS_CHECKLIST.map((i) => [i, 'ok'])))
  const [commentaires, setCommentaires] = useState({})
  const [messageChecklist, setMessageChecklist] = useState('')
  const [messageDemarrage, setMessageDemarrage] = useState({})
  const [incidentOuvert, setIncidentOuvert] = useState(null)
  const [incident, setIncident] = useState(INCIDENT_VIDE)
  const [messageIncident, setMessageIncident] = useState({ type: '', texte: '' })
  // Sans cela, « Aucune feuille de route » s'afficherait pendant le chargement et tromperait le chauffeur.
  const [charge, setCharge] = useState(false)

  function chargerFeuilles() {
    return Promise.all([apiFetch('/feuilles-de-route/'), apiFetch('/departs/'), apiFetch('/lignes/')]).then(
      ([feuillesData, departsData, lignesData]) => {
        const lignesParId = Object.fromEntries(lignesData.map((l) => [l.id, l]))
        const departsParId = Object.fromEntries(departsData.map((d) => [d.id, d]))
        const mesFeuillesDuJour = feuillesData.filter(
          (f) => f.chauffeur === user.id && estAujourdhui(f.heure_depart_prevue),
        )
        setFeuilles(
          mesFeuillesDuJour.map((f) => ({
            ...f,
            ligneNom: lignesParId[departsParId[f.depart]?.ligne]?.nom,
            vehicule: departsParId[f.depart]?.vehicule,
          })),
        )
        setLignes(lignesParId)
      },
    )
  }

  useEffect(() => {
    chargerFeuilles()
      .catch((err) => setError(err.message))
      .finally(() => setCharge(true))
  }, [user.id])

  async function envoyerChecklist(feuilleId) {
    setMessageChecklist('')
    try {
      for (const item of ITEMS_CHECKLIST) {
        await apiFetch('/checklists/', {
          method: 'POST',
          body: {
            feuille_de_route: feuilleId,
            item,
            etat: etats[item],
            commentaire: commentaires[item] || '',
          },
        })
      }
      const defauts = ITEMS_CHECKLIST.filter((item) => etats[item] === 'defaut')
      setMessageChecklist(
        defauts.length > 0
          ? `Checklist enregistrée. Défaut signalé sur : ${defauts.join(', ')}.`
          : 'Checklist enregistrée, aucun défaut.',
      )
      setChecklistOuverte(null)
    } catch (err) {
      setMessageChecklist(err.message)
    }
  }

  async function signalerIncident(event, feuille) {
    event.preventDefault()
    setMessageIncident({ type: '', texte: '' })
    try {
      await apiFetch('/incidents/', {
        method: 'POST',
        body: { feuille_de_route: feuille.id, vehicule: feuille.vehicule, chauffeur: user.id, ...incident },
      })
      setMessageIncident({
        type: 'success',
        texte: 'Incident signalé. Il apparaît sur les tableaux de bord de l’exploitation et du QHSE.',
      })
      setIncident(INCIDENT_VIDE)
      setIncidentOuvert(null)
    } catch (err) {
      setMessageIncident({ type: 'error', texte: err.message })
    }
  }

  async function arriver(feuilleId) {
    setMessageDemarrage((prev) => ({ ...prev, [feuilleId]: '' }))
    try {
      await apiFetch(`/feuilles-de-route/${feuilleId}/arriver/`, { method: 'POST' })
      setMessageDemarrage((prev) => ({ ...prev, [feuilleId]: 'success:Arrivée enregistrée, le départ est terminé.' }))
      await chargerFeuilles()
    } catch (err) {
      setMessageDemarrage((prev) => ({ ...prev, [feuilleId]: `error:${err.message}` }))
    }
  }

  async function demarrer(feuilleId) {
    setMessageDemarrage((prev) => ({ ...prev, [feuilleId]: '' }))
    try {
      await apiFetch(`/feuilles-de-route/${feuilleId}/demarrer/`, { method: 'POST' })
      setMessageDemarrage((prev) => ({ ...prev, [feuilleId]: 'success:Feuille de route démarrée.' }))
      await chargerFeuilles()
    } catch (err) {
      setMessageDemarrage((prev) => ({ ...prev, [feuilleId]: `error:${err.message}` }))
    }
  }

  return (
    <Layout title="Tableau de bord — Chauffeur">
      <Alert>{error}</Alert>
      {!charge && !error && <p>Chargement…</p>}
      {charge && feuilles.length === 0 && !error && <p>Aucune feuille de route prévue aujourd'hui.</p>}

      {feuilles.map((feuille) => {
        const messageDemarrageBrut = messageDemarrage[feuille.id] || ''
        const [typeMsg, texteMsg] = messageDemarrageBrut.includes(':')
          ? messageDemarrageBrut.split(':', 2)
          : ['', '']

        return (
          <section className="card" key={feuille.id}>
            <h2>{feuille.ligneNom || 'Ligne'}</h2>
            <p>Départ prévu : {new Date(feuille.heure_depart_prevue).toLocaleString('fr-FR')}</p>
            <p>
              Statut :{' '}
              {feuille.heure_arrivee_reelle
                ? `arrivé à ${new Date(feuille.heure_arrivee_reelle).toLocaleTimeString('fr-FR')}`
                : feuille.heure_depart_reelle
                  ? `parti à ${new Date(feuille.heure_depart_reelle).toLocaleTimeString('fr-FR')}`
                  : 'pas encore parti'}
            </p>

            <div className="button-row">
              <button type="button" onClick={() => setChecklistOuverte(feuille.id)}>
                Remplir la checklist avant-départ
              </button>
              <button
                type="button"
                onClick={() => demarrer(feuille.id)}
                disabled={Boolean(feuille.heure_depart_reelle)}
              >
                Démarrer
              </button>
              <button
                type="button"
                className="button-secondary"
                onClick={() => arriver(feuille.id)}
                disabled={!feuille.heure_depart_reelle || Boolean(feuille.heure_arrivee_reelle)}
              >
                Signaler l’arrivée
              </button>
              <button
                type="button"
                className="button-secondary"
                onClick={() => setIncidentOuvert(incidentOuvert === feuille.id ? null : feuille.id)}
              >
                Signaler un incident
              </button>
            </div>
            {typeMsg && <Alert type={typeMsg === 'success' ? 'success' : 'error'}>{texteMsg}</Alert>}

            {incidentOuvert === feuille.id && (
              <form className="checklist-form" onSubmit={(e) => signalerIncident(e, feuille)}>
                <div className="form-grid">
                  <label>
                    Type
                    <select
                      value={incident.type_incident}
                      onChange={(e) => setIncident({ ...incident, type_incident: e.target.value })}
                    >
                      {Object.entries(LABELS_TYPE_INCIDENT).map(([valeur, label]) => (
                        <option key={valeur} value={valeur}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Gravité
                    <select
                      value={incident.gravite}
                      onChange={(e) => setIncident({ ...incident, gravite: e.target.value })}
                    >
                      {Object.entries(LABELS_GRAVITE).map(([valeur, label]) => (
                        <option key={valeur} value={valeur}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Description
                    <input
                      value={incident.description}
                      onChange={(e) => setIncident({ ...incident, description: e.target.value })}
                      required
                    />
                  </label>
                </div>
                <button type="submit">Envoyer le signalement</button>
              </form>
            )}

            {checklistOuverte === feuille.id && (
              <div className="checklist-form">
                {ITEMS_CHECKLIST.map((item) => (
                  <div className="checklist-row" key={item}>
                    <span className="checklist-item-label">{item}</span>
                    <select
                      value={etats[item]}
                      onChange={(e) => setEtats((prev) => ({ ...prev, [item]: e.target.value }))}
                    >
                      <option value="ok">OK</option>
                      <option value="defaut">Défaut</option>
                    </select>
                    <input
                      type="text"
                      placeholder="Commentaire (optionnel)"
                      value={commentaires[item] || ''}
                      onChange={(e) =>
                        setCommentaires((prev) => ({ ...prev, [item]: e.target.value }))
                      }
                    />
                  </div>
                ))}
                <button type="button" onClick={() => envoyerChecklist(feuille.id)}>
                  Valider la checklist
                </button>
              </div>
            )}
          </section>
        )
      })}

      <Alert type={messageChecklist.startsWith('Checklist enregistrée') ? 'success' : 'error'}>
        {messageChecklist}
      </Alert>
      <Alert type={messageIncident.type || 'error'}>{messageIncident.texte}</Alert>
    </Layout>
  )
}
