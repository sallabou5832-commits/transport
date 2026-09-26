import { useEffect, useRef, useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import ChecklistReprise from './ChecklistReprise.jsx'

const INTERVALLE_ENVOI_MS = 20000

function duree(minutes) {
  return `${Math.floor(minutes / 60)} h ${String(minutes % 60).padStart(2, '0')}`
}

/**
 * Suivi du trajet en cours pour le conducteur : GPS (positions envoyées par lots, un lot en attente est conservé tant qu'il
 * n'est pas parti : zone sans réseau), temps de conduite continue avec pause, relais, anomalie de cargaison. N'apparaît que
 * pendant un trajet.
 */
export default function SuiviTrajet() {
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [gps, setGps] = useState({ actif: false, derniere: null, erreur: '' })
  const [relais, setRelais] = useState({ id: '', lieu: '' })
  const [anomalie, setAnomalie] = useState('')
  const [envoi, setEnvoi] = useState(false)
  const tampon = useRef([])
  const surveillance = useRef(null)
  const premierReleve = useRef(true)

  const { data, recharger } = useChargement(() => apiFetch('/suivi/moi/'), { intervalleMs: 30000 })

  async function vider() {
    if (tampon.current.length === 0) return
    const lot = tampon.current.splice(0)
    try {
      await apiFetch('/positions/', { method: 'POST', body: lot })
      setGps((etat) => ({ ...etat, derniere: new Date(), erreur: '' }))
    } catch (err) {
      tampon.current.unshift(...lot) // on garde le lot pour le renvoyer : pas de position perdue
      setGps((etat) => ({ ...etat, erreur: `Envoi différé : ${err.message}` }))
    }
  }

  function demarrerGps() {
    if (!navigator.geolocation) {
      setGps({ actif: false, derniere: null, erreur: 'Ce navigateur ne sait pas se géolocaliser.' })
      return
    }
    surveillance.current = navigator.geolocation.watchPosition(
      (position) => {
        tampon.current.push({
          latitude: position.coords.latitude.toFixed(6),
          longitude: position.coords.longitude.toFixed(6),
          vitesse_kmh: position.coords.speed ? Math.round(position.coords.speed * 3.6) : null,
          releve_le: new Date(position.timestamp).toISOString(),
        })
        // La première position part tout de suite : la régulation voit le car sans attendre le premier lot.
        if (premierReleve.current) {
          premierReleve.current = false
          vider()
        }
      },
      (erreur) => setGps((etat) => ({ ...etat, erreur: `Géolocalisation impossible : ${erreur.message}` })),
      { enableHighAccuracy: true, maximumAge: 10000 },
    )
    premierReleve.current = true
    setGps({ actif: true, derniere: null, erreur: '' })
  }

  function arreterGps() {
    if (surveillance.current !== null) navigator.geolocation.clearWatch(surveillance.current)
    surveillance.current = null
    vider()
    setGps((etat) => ({ ...etat, actif: false }))
  }

  useEffect(() => {
    if (!gps.actif) return undefined
    const minuteur = setInterval(vider, INTERVALLE_ENVOI_MS)
    return () => clearInterval(minuteur)
  }, [gps.actif])

  useEffect(() => () => surveillance.current !== null && navigator.geolocation.clearWatch(surveillance.current), [])

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

  // Après un relais réussi le conducteur n'a plus de trajet : on garde la confirmation à l'écran.
  if (!data?.en_cours) return message.texte ? <Alert type={message.type || 'error'}>{message.texte}</Alert> : null
  const { fatigue, feuille_de_route: feuille } = data
  const avancement = Math.min(100, Math.round((100 * fatigue.conduite_continue_minutes) / fatigue.seuil_minutes))

  return (
    <section className="card" aria-label="Suivi du trajet en cours">
      <h2>Trajet en cours : {data.ligne}</h2>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      {data.reprise_a_faire && (
        <ChecklistReprise
          reprise={data.reprise_a_faire}
          onFait={async (texte) => {
            await recharger()
            setMessage({ type: 'success', texte })
          }}
        />
      )}

      <h3>Suivi GPS</h3>
      {gps.actif ? (
        <p>
          Suivi actif{gps.derniere ? ` — dernière position envoyée à ${gps.derniere.toLocaleTimeString('fr-FR')}` : ' — en attente de la première position'}.{' '}
          <button type="button" className="button-secondary button-small" onClick={arreterGps}>
            Arrêter le suivi
          </button>
        </p>
      ) : (
        <p>
          Votre position n’est pas envoyée à la régulation.{' '}
          <button type="button" className="button-small" onClick={demarrerGps}>
            Activer le suivi GPS
          </button>
        </p>
      )}
      <Alert type="warning">{gps.erreur}</Alert>

      <h3>Temps de conduite</h3>
      <p>
        {fatigue.en_pause ? 'En pause. ' : ''}
        {duree(fatigue.conduite_continue_minutes)} de conduite continue
        {fatigue.alerte ? '' : ` — alerte dans ${duree(fatigue.minutes_avant_alerte)}`}.
      </p>
      <span
        className={`jeu-barre${fatigue.alerte ? ' barre-alerte' : ''}`}
        role="progressbar"
        aria-label="Temps de conduite continue"
        aria-valuenow={avancement}
        aria-valuemin={0}
        aria-valuemax={100}
        style={{ width: '100%' }}
      >
        <span style={{ width: `${avancement}%` }} />
      </span>
      {fatigue.alerte && !fatigue.en_pause && (
        <Alert type="warning">
          Vous conduisez depuis plus de {duree(fatigue.seuil_minutes)} : faites une pause ou organisez un relais.
        </Alert>
      )}
      <div className="button-row">
        {fatigue.en_pause ? (
          <button
            type="button"
            disabled={envoi}
            onClick={() =>
              agir(() => apiFetch(`/feuilles-de-route/${feuille}/pause/`, { method: 'POST', body: { action: 'fin' } }), 'Pause terminée : le compteur repart de zéro.')
            }
          >
            Terminer la pause
          </button>
        ) : (
          <button
            type="button"
            className="button-secondary"
            disabled={envoi}
            onClick={() =>
              agir(() => apiFetch(`/feuilles-de-route/${feuille}/pause/`, { method: 'POST', body: { action: 'debut' } }), 'Pause commencée.')
            }
          >
            Commencer une pause
          </button>
        )}
      </div>

      {fatigue.relais_suggeres?.length > 0 && (
        <>
          <h3>Passer le relais</h3>
          <form
            onSubmit={(event) => {
              event.preventDefault()
              agir(
                () => apiFetch(`/feuilles-de-route/${feuille}/relais/`, { method: 'POST', body: { relais: Number(relais.id), lieu: relais.lieu } }),
                'Relais effectué : la feuille de route est transférée, le nouveau conducteur et la régulation sont prévenus.',
              )
            }}
          >
            <div className="form-grid">
              <label>
                Conducteur qui reprend
                <select value={relais.id} onChange={(e) => setRelais({ ...relais, id: e.target.value })} required>
                  <option value="">— Choisir —</option>
                  {fatigue.relais_suggeres.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.nom}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Lieu du relais
                <input value={relais.lieu} onChange={(e) => setRelais({ ...relais, lieu: e.target.value })} required />
              </label>
            </div>
            <div className="button-row">
              <button type="submit" disabled={envoi}>
                Passer le relais
              </button>
            </div>
          </form>
        </>
      )}

      <h3>Surveillance de la cargaison</h3>
      <form
        onSubmit={async (event) => {
          event.preventDefault()
          const ok = await agir(
            () => apiFetch(`/feuilles-de-route/${feuille}/anomalie-cargaison/`, { method: 'POST', body: { description: anomalie } }),
            'Anomalie signalée : la régulation, la direction et le QHSE sont alertés.',
          )
          if (ok) setAnomalie('')
        }}
      >
        <div className="form-grid">
          <label>
            Anomalie constatée
            <input value={anomalie} onChange={(e) => setAnomalie(e.target.value)} minLength={5} required />
          </label>
        </div>
        <div className="button-row">
          <button type="submit" className="button-secondary" disabled={envoi}>
            Signaler l’anomalie
          </button>
        </div>
      </form>
    </section>
  )
}
