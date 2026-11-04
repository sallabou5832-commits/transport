import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch, chargeDuJeton, getRefreshToken, setTokens } from '../api/client.js'
import useActions from '../api/useActions.js'
import useChargement from '../api/useChargement.js'
import { useAuth } from '../auth/AuthContext.jsx'
import { dashboardPathForRole } from '../auth/roles.js'
import Alert from '../components/Alert.jsx'
import Layout from '../components/Layout.jsx'
import { LABELS_DUREE_SESSION, formatDateHeure } from '../lib/format.js'

const MODES_VOCAUX = [
  ['', 'Comme réglé par mon supérieur'],
  ['true', 'Oui, je préfère dicter'],
  ['false', 'Non'],
]

const VIDE = { ancien: '', nouveau: '', confirmation: '' }

/** La session de cet appareil, lue dans son jeton de renouvellement : durée accordée et échéance. */
function sessionDeCetAppareil() {
  const charge = chargeDuJeton(getRefreshToken() || '')
  if (!charge) return null
  return { duree: charge.duree || 'jour', expireLe: new Date(charge.exp * 1000).toISOString() }
}

function MotDePasse({ provisoire, onSessionRenouvelee }) {
  const [valeurs, setValeurs] = useState(VIDE)
  const { agir, envoi, message, setMessage } = useActions()
  const changer = (champ) => (event) => setValeurs({ ...valeurs, [champ]: event.target.value })

  async function enregistrer(event) {
    event.preventDefault()
    if (valeurs.nouveau !== valeurs.confirmation) {
      setMessage({ type: 'error', texte: 'La confirmation ne correspond pas au nouveau mot de passe.' })
      return
    }
    const ok = await agir(async () => {
      const jetons = await apiFetch('/auth/mot-de-passe/', {
        method: 'POST',
        body: { ancien: valeurs.ancien, nouveau: valeurs.nouveau, refresh: getRefreshToken() },
      })
      setTokens(jetons.access, jetons.refresh)
      onSessionRenouvelee()
    }, 'Mot de passe changé. Vos autres appareils devront se reconnecter avec le nouveau.')
    if (ok) setValeurs(VIDE)
  }

  return (
    <section className="card">
      <h2>Mot de passe</h2>
      {provisoire && (
        <p>
          <strong>Votre mot de passe est provisoire.</strong> Choisissez le vôtre pour accéder à votre espace : celui qui vous a
          remis le mot de passe provisoire ne le connaîtra pas.
        </p>
      )}
      <form onSubmit={enregistrer}>
        <Alert type={message.type || 'error'}>{message.texte}</Alert>
        <div className="form-grid">
          <label>
            {provisoire ? 'Mot de passe provisoire' : 'Mot de passe actuel'}
            <input type="password" value={valeurs.ancien} onChange={changer('ancien')} autoComplete="current-password" required />
          </label>
          <label>
            Nouveau mot de passe
            <input
              type="password"
              value={valeurs.nouveau}
              onChange={changer('nouveau')}
              autoComplete="new-password"
              minLength={8}
              required
            />
          </label>
          <label>
            Confirmation
            <input
              type="password"
              value={valeurs.confirmation}
              onChange={changer('confirmation')}
              autoComplete="new-password"
              minLength={8}
              required
            />
          </label>
        </div>
        <p className="muted">
          8 caractères au moins, ni trop courant, ni proche de votre identifiant, pas uniquement des chiffres.
        </p>
        <div className="fiche-actions">
          <button type="submit" disabled={envoi}>
            Changer le mot de passe
          </button>
        </div>
      </form>
    </section>
  )
}

function Session({ session, politique, onSessionRenouvelee }) {
  const { agir, envoi, message } = useActions()

  function fermerLesAutres() {
    agir(async () => {
      const jetons = await apiFetch('/auth/fermer-autres-sessions/', { method: 'POST', body: { refresh: getRefreshToken() } })
      setTokens(jetons.access, jetons.refresh)
      onSessionRenouvelee()
    }, 'Vos autres appareils sont déconnectés. Cet appareil reste connecté.')
  }

  return (
    <section className="card">
      <h2>Session</h2>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      {session ? (
        <p>
          Cet appareil reste connecté jusqu&apos;au <strong>{formatDateHeure(session.expireLe)}</strong> (
          {LABELS_DUREE_SESSION[session.duree] || session.duree}), puis le mot de passe vous sera redemandé.
        </p>
      ) : (
        <p className="muted">Session de cet appareil illisible : reconnectez-vous.</p>
      )}
      <p className="muted">
        Pour une autre durée, déconnectez-vous puis cochez « Rester connecté » à la connexion.
        {politique && ` Durée la plus longue permise pour votre poste : ${LABELS_DUREE_SESSION[politique.duree_max].toLowerCase()}.`}
      </p>
      {politique?.code_court_exige && (
        <p className="muted">Votre compagnie exige un code court pour rouvrir l&apos;application mobile.</p>
      )}
      <div className="fiche-actions">
        <button type="button" className="button-secondary" disabled={envoi || !session} onClick={fermerLesAutres}>
          Déconnecter mes autres appareils
        </button>
      </div>
    </section>
  )
}

function Preferences() {
  const { data: preferences, error, recharger } = useChargement(() => apiFetch('/configuration/mes-preferences/'))
  const { agir, envoi, message, setMessage } = useActions(recharger)
  // Le choix en cours d'envoi, affiché tout de suite ; un refus du serveur rend la valeur enregistrée.
  const [attente, setAttente] = useState({})
  const valeur = (champ) => (champ in attente ? attente[champ] : preferences[champ])

  async function enregistrer(champs, confirmation) {
    setAttente(champs)
    await agir(() => apiFetch('/configuration/mes-preferences/', { method: 'PATCH', body: champs }), confirmation)
    setAttente({})
  }

  async function notifications(active) {
    if (active && window.Notification?.permission !== 'granted') {
      const permission = window.Notification ? await window.Notification.requestPermission() : 'denied'
      if (permission !== 'granted') {
        setMessage({ type: 'error', texte: 'Le navigateur refuse les notifications : autorisez-les pour ce site, puis réessayez.' })
        return
      }
    }
    enregistrer({ notifications_navigateur: active }, active ? 'Notifications activées.' : 'Notifications désactivées.')
  }

  return (
    <section className="card">
      <h2>Préférences</h2>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      {preferences && (
        <div className="form-grid">
          <label>
            Mode vocal (application mobile)
            <select
              value={valeur('prefere_vocal') === null ? '' : String(valeur('prefere_vocal'))}
              disabled={envoi || preferences.vocal_impose}
              onChange={(e) =>
                enregistrer(
                  { prefere_vocal: e.target.value === '' ? null : e.target.value === 'true' },
                  'Mode vocal enregistré.',
                )
              }
            >
              {MODES_VOCAUX.map(([valeur, libelle]) => (
                <option key={valeur} value={valeur}>
                  {libelle}
                </option>
              ))}
            </select>
            {preferences.vocal_impose && <span className="muted">Fixé par votre supérieur.</span>}
          </label>
          <label className="checkbox-ligne">
            <input
              type="checkbox"
              checked={valeur('son_alertes')}
              disabled={envoi}
              onChange={(e) =>
                enregistrer({ son_alertes: e.target.checked }, e.target.checked ? 'Son activé.' : 'Son désactivé.')
              }
            />
            Un son à l&apos;arrivée d&apos;une alerte critique
          </label>
          <label className="checkbox-ligne">
            <input
              type="checkbox"
              checked={valeur('notifications_navigateur')}
              disabled={envoi}
              onChange={(e) => notifications(e.target.checked)}
            />
            Une notification du navigateur pour une alerte critique, quand l&apos;onglet est en arrière-plan
          </label>
        </div>
      )}
    </section>
  )
}

/**
 * Mes paramètres, pour chacun : changer son mot de passe, voir la durée de sa session et fermer celles de ses autres appareils.
 * La durée se choisit à la connexion (« Rester connecté »), sous le plafond de la compagnie et du poste.
 */
export default function MesParametresPage() {
  const { user, rafraichirUtilisateur } = useAuth()
  const navigate = useNavigate()
  const [session, setSession] = useState(sessionDeCetAppareil)
  const { data: configuration, error } = useChargement(() => apiFetch('/configuration/moi/'))
  const provisoire = Boolean(user?.doit_changer_mot_de_passe)
  const relireSession = () => setSession(sessionDeCetAppareil())

  async function apresMotDePasse() {
    relireSession()
    if (provisoire) {
      // Le mot de passe provisoire est remplacé : l'agent arrive enfin sur son espace.
      const me = await rafraichirUtilisateur()
      navigate(dashboardPathForRole(me.role), { replace: true })
    }
  }

  return (
    <Layout title="Mes paramètres">
      <Alert>{error}</Alert>
      <MotDePasse provisoire={provisoire} onSessionRenouvelee={apresMotDePasse} />
      {!provisoire && <Session session={session} politique={configuration?.session} onSessionRenouvelee={relireSession} />}
      {!provisoire && <Preferences />}
    </Layout>
  )
}
