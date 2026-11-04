import { useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../api/client.js'
import useActions from '../api/useActions.js'
import useChargement from '../api/useChargement.js'
import { useAuth } from '../auth/AuthContext.jsx'
import { ROLE_LABELS } from '../auth/roles.js'
import Alert from '../components/Alert.jsx'
import Badge from '../components/Badge.jsx'
import Layout from '../components/Layout.jsx'
import { formatDateHeure, identifiantPropose } from '../lib/format.js'

// Les postes qu'on donne à un compte ici : ni PDG, ni opérateur de la plateforme.
const POSTES = Object.entries(ROLE_LABELS).filter(([valeur]) => !['pdg', 'superadmin'].includes(valeur))
// Les postes qu'on rattache à une gare dès la création (l'équipe locale) ; le chef d'une gare se désigne dans « Gares et quais ».
const EQUIPE_LOCALE = ['guichetier', 'bagagiste']
const FICHE = ['first_name', 'last_name', 'role', 'telephone', 'matricule', 'email']
const VIDE = { username: '', first_name: '', last_name: '', role: 'guichetier', telephone: '', matricule: '', email: '', gare: '', date_embauche: '' }

function MotDePasseProvisoire({ resultat, onFermer }) {
  return (
    <section className="card card-highlight">
      <h2>Mot de passe provisoire de {resultat.nom}</h2>
      <p>
        Identifiant : <strong>{resultat.username}</strong> — mot de passe provisoire :{' '}
        <code className="mot-de-passe-provisoire">{resultat.mot_de_passe_provisoire}</code>
      </p>
      <p className="muted">
        Remettez-le à l&apos;agent : il devra choisir le sien à sa première connexion, et ne pourra rien faire d&apos;autre avant.
        Il ne sera plus affiché.
      </p>
      <div className="fiche-actions">
        <button type="button" className="button-secondary" onClick={onFermer}>
          C&apos;est noté
        </button>
      </div>
    </section>
  )
}

function NouveauCompte({ gares, onCree }) {
  const [valeurs, setValeurs] = useState(VIDE)
  const { agir, envoi, message } = useActions()

  function changer(champ) {
    return (event) => {
      const suivantes = { ...valeurs, [champ]: event.target.value }
      // L'identifiant suit le prénom et le nom tant qu'on ne l'a pas changé à la main.
      if (champ !== 'username' && valeurs.username === identifiantPropose(valeurs.first_name, valeurs.last_name)) {
        suivantes.username = identifiantPropose(suivantes.first_name, suivantes.last_name)
      }
      if (champ === 'role' && !EQUIPE_LOCALE.includes(suivantes.role)) suivantes.gare = ''
      setValeurs(suivantes)
    }
  }

  async function creer(event) {
    event.preventDefault()
    const corps = { ...valeurs, gare: valeurs.gare ? Number(valeurs.gare) : null, date_embauche: valeurs.date_embauche || null }
    let resultat = null
    const ok = await agir(async () => {
      resultat = await apiFetch('/comptes/', { method: 'POST', body: corps })
    })
    if (ok) {
      setValeurs(VIDE)
      onCree(resultat)
    }
  }

  return (
    <section className="card">
      <h2>Nouveau compte</h2>
      <form onSubmit={creer}>
        <Alert type={message.type || 'error'}>{message.texte}</Alert>
        <div className="form-grid">
          <label>
            Prénom
            <input value={valeurs.first_name} onChange={changer('first_name')} maxLength={150} required />
          </label>
          <label>
            Nom
            <input value={valeurs.last_name} onChange={changer('last_name')} maxLength={150} required />
          </label>
          <label>
            Identifiant de connexion
            <input value={valeurs.username} onChange={changer('username')} maxLength={150} pattern="[\w.@+\-]+" required />
          </label>
          <label>
            Poste
            <select value={valeurs.role} onChange={changer('role')}>
              {POSTES.map(([valeur, libelle]) => (
                <option key={valeur} value={valeur}>
                  {libelle}
                </option>
              ))}
            </select>
          </label>
          {EQUIPE_LOCALE.includes(valeurs.role) && (
            <label>
              Gare
              <select value={valeurs.gare} onChange={changer('gare')}>
                <option value="">— Plus tard (le chef de gare l&apos;affectera) —</option>
                {gares.map((gare) => (
                  <option key={gare.id} value={gare.id}>
                    {gare.nom}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label>
            Téléphone
            <input type="tel" value={valeurs.telephone} onChange={changer('telephone')} maxLength={30} />
          </label>
          <label>
            Matricule
            <input value={valeurs.matricule} onChange={changer('matricule')} maxLength={30} />
          </label>
          <label>
            Courriel
            <input type="email" value={valeurs.email} onChange={changer('email')} maxLength={254} />
          </label>
          <label>
            Date d&apos;embauche (ouvre le dossier agent)
            <input type="date" value={valeurs.date_embauche} onChange={changer('date_embauche')} />
          </label>
        </div>
        <p className="muted">Un mot de passe provisoire est créé et vous est montré une seule fois, pour le remettre à l&apos;agent.</p>
        <div className="fiche-actions">
          <button type="submit" disabled={envoi}>
            Créer le compte
          </button>
        </div>
      </form>
    </section>
  )
}

function FicheCompte({ compte, onEnregistre }) {
  const [valeurs, setValeurs] = useState(() => Object.fromEntries(FICHE.map((champ) => [champ, compte[champ] ?? ''])))
  const { agir, envoi, message } = useActions(onEnregistre)
  const changer = (champ) => (event) => setValeurs({ ...valeurs, [champ]: event.target.value })

  function enregistrer(event) {
    event.preventDefault()
    agir(() => apiFetch(`/comptes/${compte.id}/`, { method: 'PATCH', body: valeurs }), `Fiche de ${compte.nom} enregistrée.`)
  }

  return (
    <form onSubmit={enregistrer}>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      <div className="form-grid">
        <label>
          Prénom
          <input value={valeurs.first_name} onChange={changer('first_name')} maxLength={150} required />
        </label>
        <label>
          Nom
          <input value={valeurs.last_name} onChange={changer('last_name')} maxLength={150} required />
        </label>
        <label>
          Poste
          <select value={valeurs.role} onChange={changer('role')}>
            {POSTES.map(([valeur, libelle]) => (
              <option key={valeur} value={valeur}>
                {libelle}
              </option>
            ))}
          </select>
        </label>
        <label>
          Téléphone
          <input type="tel" value={valeurs.telephone} onChange={changer('telephone')} maxLength={30} />
        </label>
        <label>
          Matricule
          <input value={valeurs.matricule} onChange={changer('matricule')} maxLength={30} />
        </label>
        <label>
          Courriel
          <input type="email" value={valeurs.email} onChange={changer('email')} maxLength={254} />
        </label>
      </div>
      {valeurs.role !== compte.role && (
        <p className="muted">Changer de poste déconnecte l&apos;agent : il retrouvera son nouvel espace à sa prochaine connexion.</p>
      )}
      <div className="fiche-actions">
        <button type="submit" disabled={envoi}>
          Enregistrer la fiche
        </button>
      </div>
    </form>
  )
}

function EtatCompte({ compte }) {
  if (!compte.actif) return <Badge ton="rouge">Suspendu</Badge>
  if (compte.doit_changer_mot_de_passe) return <Badge ton="orange">Mot de passe provisoire</Badge>
  return <Badge ton="vert">Actif</Badge>
}

/**
 * Personnel et comptes : le PDG (et le DRH, si le règlement intérieur le lui permet) crée les comptes à l'embauche, tient leur
 * fiche (poste, téléphone, matricule) et réinitialise un mot de passe oublié. Suspendre un compte reste un pouvoir du PDG
 * (page Pilotage).
 */
export default function PersonnelPage() {
  const { user } = useAuth()
  const [role, setRole] = useState('')
  const [recherche, setRecherche] = useState('')
  const [ouvert, setOuvert] = useState(null)
  const [provisoire, setProvisoire] = useState(null)
  const { agir, envoi, message } = useActions()
  const { data: comptes, error, loading, recharger } = useChargement(
    () => apiFetch(`/comptes/?role=${role}&q=${encodeURIComponent(recherche)}`),
    { cle: `${role}|${recherche}` },
  )
  const { data: gares } = useChargement(() => apiFetch('/gares/'))

  function reinitialiser(compte) {
    if (!window.confirm(`Réinitialiser le mot de passe de ${compte.nom} ? Ses sessions ouvertes seront fermées.`)) return
    agir(async () => {
      setProvisoire(await apiFetch(`/comptes/${compte.id}/reinitialiser-mot-de-passe/`, { method: 'POST' }))
      await recharger()
    })
  }

  async function apresCreation(resultat) {
    setProvisoire(resultat)
    await recharger()
  }

  const compte = comptes?.find((c) => c.id === ouvert) || null

  return (
    <Layout title="Personnel et comptes">
      {provisoire && <MotDePasseProvisoire resultat={provisoire} onFermer={() => setProvisoire(null)} />}
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      {error ? (
        <Alert>{error}</Alert>
      ) : (
        <>
          <section className="card">
            <h2>Comptes du personnel</h2>
            <div className="toolbar">
              <label>
                Rechercher
                <input
                  type="search"
                  placeholder="Nom, identifiant ou matricule"
                  value={recherche}
                  onChange={(e) => setRecherche(e.target.value)}
                />
              </label>
              <label>
                Poste
                <select value={role} onChange={(e) => setRole(e.target.value)}>
                  <option value="">Tous</option>
                  {POSTES.map(([valeur, libelle]) => (
                    <option key={valeur} value={valeur}>
                      {libelle}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {user?.role === 'pdg' && (
              <p className="muted">
                Suspendre ou réactiver un compte : <Link to="/pilotage">Pilotage</Link>. Confier la gestion des comptes au DRH :{' '}
                <Link to="/cadre">Cadre de la compagnie</Link>.
              </p>
            )}
            {!comptes ? (
              loading && <p>Chargement…</p>
            ) : comptes.length === 0 ? (
              <p className="muted">Aucun compte.</p>
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Agent</th>
                      <th>Poste</th>
                      <th>Matricule</th>
                      <th>Téléphone</th>
                      <th>Gare</th>
                      <th>État</th>
                      <th>Dernière connexion</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {comptes.map((c) => (
                      <tr key={c.id}>
                        <td>
                          {c.nom}
                          <div className="muted">
                            {c.username}
                            {!c.a_un_dossier && ' · sans dossier agent'}
                          </div>
                        </td>
                        <td>{c.role_libelle}</td>
                        <td>{c.matricule || '—'}</td>
                        <td>{c.telephone || '—'}</td>
                        <td>{c.gare || '—'}</td>
                        <td>
                          <EtatCompte compte={c} />
                        </td>
                        <td>{c.last_login ? formatDateHeure(c.last_login) : <span className="muted">Jamais</span>}</td>
                        <td>
                          <div className="button-row">
                            <button
                              type="button"
                              className="button-secondary button-small"
                              onClick={() => setOuvert(ouvert === c.id ? null : c.id)}
                            >
                              {ouvert === c.id ? 'Masquer' : 'Modifier'}
                            </button>
                            <button
                              type="button"
                              className="button-secondary button-small"
                              disabled={envoi || c.id === user?.id}
                              onClick={() => reinitialiser(c)}
                            >
                              Réinitialiser le mot de passe
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {compte && (
            <section className="card card-highlight">
              <h2>Fiche de {compte.nom}</h2>
              <FicheCompte key={compte.id} compte={compte} onEnregistre={recharger} />
            </section>
          )}

          <NouveauCompte gares={gares || []} onCree={apresCreation} />
        </>
      )}
    </Layout>
  )
}
