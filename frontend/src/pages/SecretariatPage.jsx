import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import { ROLE_LABELS } from '../auth/roles.js'
import useChargement from '../api/useChargement.js'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'
import Badge from '../components/Badge.jsx'
import { formatDate, formatDateHeure } from '../lib/format.js'

const ROLES_DE_LA_DIRECTION = [
  'pdg', 'secretaire_general', 'qhse', 'directeur_exploitation', 'directeur_technique', 'directeur_financier', 'drh', 'responsable_juridique',
]
const CATEGORIES = { courrier: 'Courrier', contrat: 'Contrat', rapport: 'Rapport', decision: 'Décision', procedure: 'Procédure', autre: 'Autre' }
const NOTE_VIDE = { titre: '', contenu: '', urgente: false, tous: false, poles: [] }
const EVENEMENT_VIDE = { titre: '', debut: '', fin: '', lieu: '', description: '', participants: [] }
const DOCUMENT_VIDE = { titre: '', categorie: 'courrier', reference: '', date_document: '', emplacement: '', mots_cles: '', description: '' }

function basculer(liste, valeur) {
  return liste.includes(valeur) ? liste.filter((v) => v !== valeur) : [...liste, valeur]
}

function useAction(recharger) {
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)
  async function agir(requete, confirmation) {
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      await requete()
      await recharger()
      setMessage({ type: 'success', texte: confirmation })
      return true
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
      return false
    } finally {
      setEnvoi(false)
    }
  }
  return { message, envoi, agir }
}

function NotesDeService() {
  const [formulaire, setFormulaire] = useState(NOTE_VIDE)
  const { data, error, recharger } = useChargement(async () => {
    const [notes, catalogue] = await Promise.all([apiFetch('/notes-service/'), apiFetch('/communication/catalogue/')])
    return { notes, catalogue }
  })
  const { message, envoi, agir } = useAction(recharger)

  async function diffuser(event) {
    event.preventDefault()
    const corps = { titre: formulaire.titre, contenu: formulaire.contenu, urgente: formulaire.urgente }
    if (formulaire.tous) corps.tous = true
    else corps.poles = formulaire.poles
    if (await agir(() => apiFetch('/notes-service/', { method: 'POST', body: corps }), 'Note diffusée : les postes concernés la reçoivent dans leur cloche d’alertes.')) {
      setFormulaire(NOTE_VIDE)
    }
  }

  if (!data) return <Alert>{error}</Alert>

  return (
    <section className="card">
      <h2>Notes de service</h2>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      <form onSubmit={diffuser}>
        <div className="form-grid">
          <label>
            Titre de la note
            <input value={formulaire.titre} onChange={(e) => setFormulaire({ ...formulaire, titre: e.target.value })} required />
          </label>
          <label>
            Contenu de la note
            <textarea rows="3" value={formulaire.contenu} onChange={(e) => setFormulaire({ ...formulaire, contenu: e.target.value })} required />
          </label>
        </div>
        <fieldset className="fonctions">
          <legend>Destinataires</legend>
          <label className="checkbox-ligne">
            <input type="checkbox" checked={formulaire.tous} onChange={(e) => setFormulaire({ ...formulaire, tous: e.target.checked })} />
            Tous les postes
          </label>
          {data.catalogue.map((pole) => (
            <label key={pole.pole} className="checkbox-ligne">
              <input
                type="checkbox"
                checked={formulaire.tous || formulaire.poles.includes(pole.pole)}
                disabled={formulaire.tous}
                onChange={() => setFormulaire({ ...formulaire, poles: basculer(formulaire.poles, pole.pole) })}
              />
              {pole.libelle}
            </label>
          ))}
          <label className="checkbox-ligne">
            <input type="checkbox" checked={formulaire.urgente} onChange={(e) => setFormulaire({ ...formulaire, urgente: e.target.checked })} />
            Note urgente
          </label>
        </fieldset>
        <div className="button-row">
          <button type="submit" disabled={envoi || (!formulaire.tous && formulaire.poles.length === 0)}>
            Diffuser la note
          </button>
        </div>
      </form>
      {data.notes.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Note</th>
                <th>Destinataires</th>
                <th>Diffusée le</th>
              </tr>
            </thead>
            <tbody>
              {data.notes.slice(0, 10).map((note) => (
                <tr key={note.id}>
                  <td>
                    <strong>{note.titre}</strong> {note.urgente && <Badge ton="orange">Urgente</Badge>}
                    <div className="muted">{note.contenu}</div>
                  </td>
                  <td>{note.roles_destinataires.length} poste(s)</td>
                  <td>
                    {formatDateHeure(note.cree_le)}
                    <div className="muted">{note.auteur_nom}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

function Agenda() {
  const [formulaire, setFormulaire] = useState(EVENEMENT_VIDE)
  const { data: evenements, error, recharger } = useChargement(() => apiFetch('/agenda/?a_venir=1'))
  const { message, envoi, agir } = useAction(recharger)

  async function ajouter(event) {
    event.preventDefault()
    const corps = {
      titre: formulaire.titre,
      debut: new Date(formulaire.debut).toISOString(),
      lieu: formulaire.lieu,
      description: formulaire.description,
      participants: formulaire.participants,
    }
    if (formulaire.fin) corps.fin = new Date(formulaire.fin).toISOString()
    if (await agir(() => apiFetch('/agenda/', { method: 'POST', body: corps }), 'Rendez-vous ajouté à l’agenda de la direction.')) setFormulaire(EVENEMENT_VIDE)
  }

  const retirer = (evenement) => agir(() => apiFetch(`/agenda/${evenement.id}/`, { method: 'DELETE' }), `« ${evenement.titre} » retiré de l'agenda.`)

  return (
    <section className="card">
      <h2>Agenda de la direction</h2>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      <form onSubmit={ajouter}>
        <div className="form-grid">
          <label>
            Titre du rendez-vous
            <input value={formulaire.titre} onChange={(e) => setFormulaire({ ...formulaire, titre: e.target.value })} required />
          </label>
          <label>
            Début
            <input type="datetime-local" value={formulaire.debut} onChange={(e) => setFormulaire({ ...formulaire, debut: e.target.value })} required />
          </label>
          <label>
            Fin (facultatif)
            <input type="datetime-local" value={formulaire.fin} onChange={(e) => setFormulaire({ ...formulaire, fin: e.target.value })} />
          </label>
          <label>
            Lieu
            <input value={formulaire.lieu} onChange={(e) => setFormulaire({ ...formulaire, lieu: e.target.value })} />
          </label>
          <label>
            Ordre du jour
            <input value={formulaire.description} onChange={(e) => setFormulaire({ ...formulaire, description: e.target.value })} />
          </label>
        </div>
        <fieldset className="fonctions">
          <legend>Invités (prévenus dans leur cloche d’alertes)</legend>
          {ROLES_DE_LA_DIRECTION.map((role) => (
            <label key={role} className="checkbox-ligne">
              <input
                type="checkbox"
                checked={formulaire.participants.includes(role)}
                onChange={() => setFormulaire({ ...formulaire, participants: basculer(formulaire.participants, role) })}
              />
              {ROLE_LABELS[role]}
            </label>
          ))}
        </fieldset>
        <div className="button-row">
          <button type="submit" disabled={envoi}>
            Ajouter à l&apos;agenda
          </button>
        </div>
      </form>
      {!evenements ? (
        <p>Chargement…</p>
      ) : evenements.length === 0 ? (
        <p className="muted">Aucun rendez-vous à venir.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Quand</th>
                <th>Rendez-vous</th>
                <th>Invités</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {evenements.map((evenement) => (
                <tr key={evenement.id}>
                  <td>{formatDateHeure(evenement.debut)}</td>
                  <td>
                    <strong>{evenement.titre}</strong>
                    <div className="muted">{[evenement.lieu, evenement.description].filter(Boolean).join(' — ')}</div>
                  </td>
                  <td>{evenement.participants.map((r) => ROLE_LABELS[r] ?? r).join(', ') || '—'}</td>
                  <td>
                    <button type="button" className="button-secondary button-small" disabled={envoi} onClick={() => retirer(evenement)}>
                      Retirer
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

function Archives() {
  const [formulaire, setFormulaire] = useState(DOCUMENT_VIDE)
  const [recherche, setRecherche] = useState('')
  const [categorie, setCategorie] = useState('')
  const [archives, setArchives] = useState('0')
  const { data: documents, error, recharger } = useChargement(
    () => apiFetch(`/archives/?q=${encodeURIComponent(recherche)}&categorie=${categorie}&archive=${archives}`),
    { cle: `${recherche}|${categorie}|${archives}` },
  )
  const { message, envoi, agir } = useAction(recharger)

  async function classer(event) {
    event.preventDefault()
    if (await agir(() => apiFetch('/archives/', { method: 'POST', body: formulaire }), `« ${formulaire.titre} » classé.`)) setFormulaire(DOCUMENT_VIDE)
  }

  const archiver = (document) => agir(() => apiFetch(`/archives/${document.id}/archiver/`, { method: 'POST', body: {} }), `« ${document.titre} » archivé.`)
  const desarchiver = (document) => agir(() => apiFetch(`/archives/${document.id}/desarchiver/`, { method: 'POST', body: {} }), `« ${document.titre} » sorti des archives.`)

  return (
    <section className="card">
      <h2>Classement et archivage</h2>
      <p className="muted">
        Le registre dit ce qu&apos;est chaque dossier administratif et où le retrouver (armoire, chemise, lien) ; il ne contient pas le
        fichier. Un dossier ne se supprime pas : il s&apos;archive.
      </p>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      <form onSubmit={classer}>
        <div className="form-grid">
          <label>
            Titre du dossier
            <input value={formulaire.titre} onChange={(e) => setFormulaire({ ...formulaire, titre: e.target.value })} required />
          </label>
          <label>
            Catégorie
            <select value={formulaire.categorie} onChange={(e) => setFormulaire({ ...formulaire, categorie: e.target.value })}>
              {Object.entries(CATEGORIES).map(([valeur, libelle]) => (
                <option key={valeur} value={valeur}>
                  {libelle}
                </option>
              ))}
            </select>
          </label>
          <label>
            Référence
            <input value={formulaire.reference} onChange={(e) => setFormulaire({ ...formulaire, reference: e.target.value })} />
          </label>
          <label>
            Date du document
            <input type="date" value={formulaire.date_document} onChange={(e) => setFormulaire({ ...formulaire, date_document: e.target.value })} required />
          </label>
          <label>
            Emplacement
            <input value={formulaire.emplacement} onChange={(e) => setFormulaire({ ...formulaire, emplacement: e.target.value })} placeholder="Armoire 3, chemise B" />
          </label>
          <label>
            Mots-clés
            <input value={formulaire.mots_cles} onChange={(e) => setFormulaire({ ...formulaire, mots_cles: e.target.value })} />
          </label>
        </div>
        <div className="button-row">
          <button type="submit" disabled={envoi}>
            Classer le dossier
          </button>
        </div>
      </form>

      <div className="toolbar">
        <label>
          Rechercher un dossier
          <input type="search" value={recherche} onChange={(e) => setRecherche(e.target.value)} placeholder="Titre, référence, mot-clé…" />
        </label>
        <label>
          Catégorie du filtre
          <select value={categorie} onChange={(e) => setCategorie(e.target.value)}>
            <option value="">Toutes</option>
            {Object.entries(CATEGORIES).map(([valeur, libelle]) => (
              <option key={valeur} value={valeur}>
                {libelle}
              </option>
            ))}
          </select>
        </label>
        <label>
          État
          <select value={archives} onChange={(e) => setArchives(e.target.value)}>
            <option value="0">Classés</option>
            <option value="1">Archivés</option>
          </select>
        </label>
      </div>
      {!documents ? (
        <p>Chargement…</p>
      ) : documents.length === 0 ? (
        <p className="muted">Aucun dossier.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Dossier</th>
                <th>Catégorie</th>
                <th>Date</th>
                <th>Où le trouver</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {documents.map((document) => (
                <tr key={document.id}>
                  <td>
                    <strong>{document.titre}</strong>
                    <div className="muted">{[document.reference, document.mots_cles].filter(Boolean).join(' — ')}</div>
                  </td>
                  <td>{document.categorie_libelle}</td>
                  <td>{formatDate(document.date_document)}</td>
                  <td>{document.emplacement || '—'}</td>
                  <td>
                    {document.archive ? (
                      <button type="button" className="button-secondary button-small" disabled={envoi} onClick={() => desarchiver(document)}>
                        Sortir des archives
                      </button>
                    ) : (
                      <button type="button" className="button-small" disabled={envoi} onClick={() => archiver(document)}>
                        Archiver
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

/** Le secrétariat de la direction : notes de service aux pôles, agenda partagé, classement et archivage des dossiers administratifs. */
export default function SecretariatPage() {
  return (
    <Layout title="Secrétariat de la direction">
      <NotesDeService />
      <Agenda />
      <Archives />
    </Layout>
  )
}
