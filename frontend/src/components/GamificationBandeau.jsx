import { useEffect, useRef, useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'

const PERIODES = [
  { id: 'semaine', label: '7 jours' },
  { id: 'mois', label: 'Ce mois' },
  { id: 'tout', label: 'Tout' },
]

/** Petit signal sonore discret (deux notes brèves) à l'accomplissement d'une mission ; coupé si l'utilisateur l'a demandé. */
function jouerSon() {
  try {
    if (localStorage.getItem('sons') === 'off') return
    const AudioContexte = window.AudioContext || window.webkitAudioContext
    if (!AudioContexte) return
    const contexte = new AudioContexte()
    ;[660, 880].forEach((frequence, index) => {
      const oscillateur = contexte.createOscillator()
      const gain = contexte.createGain()
      oscillateur.frequency.value = frequence
      gain.gain.value = 0.04
      oscillateur.connect(gain)
      gain.connect(contexte.destination)
      oscillateur.start(contexte.currentTime + index * 0.12)
      oscillateur.stop(contexte.currentTime + index * 0.12 + 0.1)
    })
  } catch {
    // le son est un plus : jamais bloquant
  }
}

function Classement({ types }) {
  const [type, setType] = useState(types[0].type)
  const [periode, setPeriode] = useState('mois')
  const { data } = useChargement(
    () => apiFetch('/gamification/classement/?type=' + type + '&periode=' + periode),
    { cle: `${type}|${periode}` },
  )

  return (
    <div>
      <div className="toolbar">
        <label>
          Classement
          <select value={type} onChange={(e) => setType(e.target.value)}>
            {types.map((t) => (
              <option key={t.type} value={t.type}>
                {t.libelle}
              </option>
            ))}
          </select>
        </label>
        <label>
          Période
          <select value={periode} onChange={(e) => setPeriode(e.target.value)}>
            {PERIODES.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      {data?.visible && (
        <ol className="classement">
          {data.classement.map((ligne) => (
            <li key={ligne.id} className={ligne.moi ? 'classement-moi' : ''}>
              <span className="classement-rang">{ligne.rang}</span>
              <span className="classement-nom">{ligne.nom}</span>
              <strong>{ligne.score} pts</strong>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

/**
 * Bandeau de jeu : niveau, points, missions du jour, badges et classements, selon le niveau de gamification de son poste
 * (voir la page de configuration). Sobre par construction : c'est un outil de travail, pas un divertissement. Absent si le
 * poste a la gamification « aucune ».
 */
export default function GamificationBandeau() {
  const [ouvert, setOuvert] = useState(false)
  const [annonce, setAnnonce] = useState(null)
  const { data } = useChargement(() => apiFetch('/gamification/moi/'), { intervalleMs: 60000 })
  const dejaAnnoncees = useRef(new Set())

  // « Mission accomplie » / « Badge remporté » : annoncé une fois, brièvement.
  useEffect(() => {
    if (!data?.actif) return undefined
    const nouvelles = [
      ...data.nouvelles.missions.map((m) => `Mission accomplie : ${m.libelle} (+${m.points} points)`),
      ...data.nouvelles.badges.map((b) => `Badge remporté : ${b.libelle} (+${b.points} points)`),
    ].filter((texte) => !dejaAnnoncees.current.has(texte))
    if (nouvelles.length === 0) return undefined
    nouvelles.forEach((texte) => dejaAnnoncees.current.add(texte))
    // Quelques succès à la fois : on en cite deux, pas dix (le détail est dans le bandeau déplié).
    const reste = nouvelles.length - 2
    setAnnonce(nouvelles.slice(0, 2).join(' · ') + (reste > 0 ? ` · et ${reste} autre(s) réussite(s)` : ''))
    jouerSon()
    const minuteur = setTimeout(() => setAnnonce(null), 8000)
    return () => clearTimeout(minuteur)
  }, [data])

  if (!data?.actif) return null
  // Un poste sans rien à marquer (direction, par exemple) n'affiche pas « niveau 1, 0 point » : seulement ses classements.
  if (!data.score_applicable && data.classements.length === 0) return null

  const missionsFaites = data.missions.filter((m) => m.accomplie).length

  return (
    <section className="jeu" aria-label="Objectifs et progression">
      {annonce && (
        <div className="jeu-annonce" role="status">
          {annonce}
        </div>
      )}
      <div className="jeu-resume">
        <button type="button" className="jeu-bouton" aria-expanded={ouvert} onClick={() => setOuvert(!ouvert)}>
          {data.score_applicable ? `Niveau ${data.niveau.numero} · ${data.niveau.nom} — ${data.points} pts` : 'Classements'}
        </button>
        {data.score_applicable && (
          <span
            className="jeu-barre"
            role="progressbar"
            aria-label="Progression vers le niveau suivant"
            aria-valuenow={data.niveau.progression_pourcent}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <span style={{ width: `${data.niveau.progression_pourcent}%` }} />
          </span>
        )}
        {data.missions.length > 0 && (
          <span className="muted">
            Missions du jour : {missionsFaites}/{data.missions.length}
          </span>
        )}
      </div>

      {ouvert && (
        <div className="jeu-detail">
          {data.missions.length > 0 && (
            <div>
              <h3>Missions du jour</h3>
              <ul className="jeu-missions">
                {data.missions.map((m) => (
                  <li key={m.code} className={m.accomplie ? 'mission-faite' : ''}>
                    <span>
                      {m.accomplie ? '✓ ' : ''}
                      {m.libelle}
                    </span>
                    <span className="jeu-barre" role="progressbar" aria-valuenow={m.progres} aria-valuemin={0} aria-valuemax={m.objectif} aria-label={m.libelle}>
                      <span style={{ width: `${Math.round((100 * m.progres) / m.objectif)}%` }} />
                    </span>
                    <span className="muted">
                      {m.progres}/{m.objectif}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {data.missions.length === 0 && <p className="muted">Pas de mission du jour pour ce poste.</p>}

          {data.badges.length > 0 && (
            <div>
              <h3>Badges</h3>
              <ul className="jeu-badges">
                {data.badges.map((b) => (
                  <li key={b.code} className={b.obtenu ? 'badge-obtenu' : 'badge-a-gagner'} title={b.description}>
                    <strong>{b.libelle}</strong>
                    <span className="muted">{b.obtenu ? (b.fois > 1 ? `remporté ${b.fois} fois` : 'remporté') : b.description}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {data.classements.length > 0 && <Classement types={data.classements} />}

          {data.points_detail.length > 0 && (
            <div>
              <h3>D’où viennent vos points</h3>
              <ul className="stat-list">
                {data.points_detail.map((ligne) => (
                  <li key={ligne.code}>
                    <span>
                      {ligne.libelle} × {ligne.nombre}
                    </span>
                    <strong>{ligne.points > 0 ? '+' : ''}{ligne.points}</strong>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
