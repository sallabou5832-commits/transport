import { useEffect, useState } from 'react'
import { apiFetch } from '../api/client.js'
import { useAuth } from '../auth/AuthContext.jsx'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'

const ITEMS_CHECKLIST = ['pneus', 'freins', 'carburant', 'eclairage', 'direction', 'ceintures']

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

  function chargerFeuilles() {
    return Promise.all([apiFetch('/feuilles-de-route/'), apiFetch('/departs/'), apiFetch('/lignes/')]).then(
      ([feuillesData, departsData, lignesData]) => {
        const lignesParId = Object.fromEntries(lignesData.map((l) => [l.id, l]))
        const departsParId = Object.fromEntries(departsData.map((d) => [d.id, d]))
        const mesFeuillesDuJour = feuillesData.filter(
          (f) => f.chauffeur === user.id && estAujourdhui(f.heure_depart_prevue),
        )
        setFeuilles(
          mesFeuillesDuJour.map((f) => ({ ...f, ligneNom: lignesParId[departsParId[f.depart]?.ligne]?.nom })),
        )
        setLignes(lignesParId)
      },
    )
  }

  useEffect(() => {
    chargerFeuilles().catch((err) => setError(err.message))
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
      {feuilles.length === 0 && !error && <p>Aucune feuille de route prévue aujourd'hui.</p>}

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
              {feuille.heure_depart_reelle
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
            </div>
            {typeMsg && <Alert type={typeMsg === 'success' ? 'success' : 'error'}>{texteMsg}</Alert>}

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
    </Layout>
  )
}
