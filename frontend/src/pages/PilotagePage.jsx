import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import { ROLE_LABELS } from '../auth/roles.js'
import useChargement from '../api/useChargement.js'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'
import Badge from '../components/Badge.jsx'
import LignesFermeture from '../components/LignesFermeture.jsx'
import ReaffectationDepart from '../components/ReaffectationDepart.jsx'
import TensionGares from '../components/TensionGares.jsx'
import { formatDateHeure, formatFCFA } from '../lib/format.js'

const STATUTS = {
  en_attente: { libelle: 'À décider', ton: 'orange' },
  valide: { libelle: 'Validé', ton: 'vert' },
  refuse: { libelle: 'Refusé', ton: 'rouge' },
}

function LigneInvestissement({ investissement, envoi, onDecider }) {
  const [commentaire, setCommentaire] = useState('')
  const enAttente = investissement.statut === 'en_attente'
  return (
    <tr>
      <td>
        <strong>{investissement.libelle}</strong>
        <div className="muted">
          {investissement.type_libelle}
          {investissement.quantite ? ` — ${investissement.quantite} véhicule(s)` : ''}
          {investissement.justification ? ` — ${investissement.justification}` : ''}
        </div>
      </td>
      <td>{formatFCFA(investissement.montant)}</td>
      <td>
        {investissement.demandeur_nom}
        <div className="muted">{formatDateHeure(investissement.cree_le)}</div>
      </td>
      <td>
        {enAttente ? (
          <input
            aria-label={`Commentaire sur ${investissement.libelle}`}
            placeholder="Commentaire (obligatoire pour un refus)"
            value={commentaire}
            onChange={(e) => setCommentaire(e.target.value)}
          />
        ) : (
          <>
            <Badge ton={STATUTS[investissement.statut].ton}>{STATUTS[investissement.statut].libelle}</Badge>
            {investissement.commentaire_decision && <div className="muted">{investissement.commentaire_decision}</div>}
          </>
        )}
      </td>
      <td className="button-row">
        {enAttente && (
          <>
            <button type="button" disabled={envoi} onClick={() => onDecider(investissement, 'valider', commentaire)}>
              Valider
            </button>
            <button type="button" disabled={envoi} className="button-secondary" onClick={() => onDecider(investissement, 'refuser', commentaire)}>
              Refuser
            </button>
          </>
        )}
      </td>
    </tr>
  )
}

function Investissements() {
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)
  const { data, error, recharger } = useChargement(() => apiFetch('/investissements/'), { intervalleMs: 60000 })

  async function decider(investissement, decision, commentaire) {
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      await apiFetch(`/investissements/${investissement.id}/decider/`, { method: 'POST', body: { decision, commentaire } })
      await recharger()
      setMessage({
        type: 'success',
        texte:
          decision === 'valider'
            ? `« ${investissement.libelle} » validé : le demandeur et la finance en sont prévenus.`
            : `« ${investissement.libelle} » refusé : le demandeur en est prévenu.`,
      })
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
    } finally {
      setEnvoi(false)
    }
  }

  const enAttente = (data ?? []).filter((i) => i.statut === 'en_attente')

  return (
    <section className="card">
      <h2>
        Investissements {enAttente.length > 0 && <Badge ton="orange">{enAttente.length} à décider</Badge>}
      </h2>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      {!data ? (
        <p>Chargement…</p>
      ) : data.length === 0 ? (
        <p className="muted">Aucune demande d&apos;investissement.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Demande</th>
                <th>Montant</th>
                <th>Demandeur</th>
                <th>Décision</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.map((investissement) => (
                <LigneInvestissement key={investissement.id} investissement={investissement} envoi={envoi} onDecider={decider} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

function CompteAgent({ compte, envoi, onAgir }) {
  const [motif, setMotif] = useState('')
  return (
    <tr className={compte.actif ? '' : 'row-danger'}>
      <td>
        <strong>{compte.nom}</strong>
        <div className="muted">{compte.username}</div>
      </td>
      <td>
        {compte.role_libelle}
        {compte.gare && <div className="muted">{compte.gare}</div>}
      </td>
      <td>
        {compte.actif ? (
          <Badge ton="vert">Actif</Badge>
        ) : (
          <>
            <Badge ton="rouge">Suspendu</Badge>
            <div className="muted">
              {compte.motif_suspension} — par {compte.suspendu_par_nom}, {formatDateHeure(compte.suspendu_le)}
            </div>
          </>
        )}
      </td>
      <td>
        <form
          className="ligne-fermeture"
          onSubmit={async (event) => {
            event.preventDefault()
            if (await onAgir(compte, compte.actif ? 'suspendre' : 'reactiver', motif)) setMotif('')
          }}
        >
          <input
            aria-label={`Motif ${compte.actif ? 'de la suspension' : 'de la réactivation'} de ${compte.nom}`}
            placeholder={compte.actif ? 'Motif (obligatoire)' : 'Commentaire (facultatif)'}
            value={motif}
            onChange={(e) => setMotif(e.target.value)}
            required={compte.actif}
          />
          <button type="submit" disabled={envoi} className={compte.actif ? 'button-danger' : ''}>
            {compte.actif ? 'Suspendre' : 'Réactiver'}
          </button>
        </form>
      </td>
    </tr>
  )
}

function Comptes() {
  const [role, setRole] = useState('')
  const [recherche, setRecherche] = useState('')
  const [suspendus, setSuspendus] = useState(false)
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)
  const { data: comptes, error, recharger } = useChargement(
    () => apiFetch(`/comptes/?role=${role}&q=${encodeURIComponent(recherche)}&suspendus=${suspendus ? 1 : 0}`),
    { cle: `${role}|${recherche}|${suspendus}` },
  )

  async function agir(compte, action, motif) {
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      if (action === 'suspendre') {
        await apiFetch(`/comptes/${compte.id}/suspendre/`, { method: 'POST', body: { motif } })
      } else {
        await apiFetch(`/comptes/${compte.id}/reactiver/`, { method: 'POST', body: { motif } })
      }
      await recharger()
      setMessage({
        type: 'success',
        texte:
          action === 'suspendre'
            ? `Compte de ${compte.nom} suspendu : il ne peut plus se connecter et ses sessions ouvertes sont coupées.`
            : `Compte de ${compte.nom} réactivé.`,
      })
      return true
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
      return false
    } finally {
      setEnvoi(false)
    }
  }

  // Le PDG et l'opérateur de la plateforme ne figurent pas dans la liste : on ne les propose pas au filtre.
  const roles = Object.entries(ROLE_LABELS).filter(([valeur]) => !['pdg', 'superadmin'].includes(valeur))

  return (
    <section className="card">
      <h2>Comptes des agents</h2>
      <p className="muted">
        Suspendre un compte coupe aussitôt son accès ; rien de ce que l&apos;agent a fait n&apos;est perdu. Chaque suspension est
        tracée au journal d&apos;audit et prévient le DRH et le chef de gare.
      </p>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      <div className="toolbar">
        <label>
          Rechercher
          <input type="search" placeholder="Nom ou identifiant" value={recherche} onChange={(e) => setRecherche(e.target.value)} />
        </label>
        <label>
          Poste
          <select value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="">Tous</option>
            {roles.map(([valeur, libelle]) => (
              <option key={valeur} value={valeur}>
                {libelle}
              </option>
            ))}
          </select>
        </label>
        <label className="checkbox-ligne">
          <input type="checkbox" checked={suspendus} onChange={(e) => setSuspendus(e.target.checked)} />
          Suspendus seulement
        </label>
      </div>
      {!comptes ? (
        <p>Chargement…</p>
      ) : comptes.length === 0 ? (
        <p>Aucun compte.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Agent</th>
                <th>Poste</th>
                <th>État</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {comptes.map((compte) => (
                <CompteAgent key={compte.id} compte={compte} envoi={envoi} onAgir={agir} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

function Reseau() {
  const { data, error, recharger } = useChargement(() => apiFetch('/dashboard/exploitation/'))
  return (
    <>
      <Alert>{error}</Alert>
      {data && <TensionGares gares={data.gares} onChange={recharger} />}
      <ReaffectationDepart />
    </>
  )
}

/**
 * Les pouvoirs d'intervention directe du PDG : geler une ligne, réaffecter un véhicule (entre gares) ou un chauffeur (sur un
 * départ), valider les investissements, suspendre un compte.
 */
export default function PilotagePage() {
  return (
    <Layout title="Pilotage — pouvoirs du PDG">
      <LignesFermeture titre="Geler ou rouvrir une ligne" />
      <Reseau />
      <Investissements />
      <Comptes />
    </Layout>
  )
}
