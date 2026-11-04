import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'
import { LABELS_DUREE_SESSION } from '../lib/format.js'

// Un réglage vide laisse le défaut : « socle » pour un poste, « comme son poste » pour un agent.
function Niveau({ etiquette, valeur, options, vide, onChange }) {
  return (
    <label>
      {etiquette}
      <select value={valeur ?? ''} onChange={(e) => onChange(e.target.value || null)}>
        <option value="">{vide}</option>
        {options.map((o) => (
          <option key={o.valeur} value={o.valeur}>
            {o.libelle}
          </option>
        ))}
      </select>
    </label>
  )
}

function Reglage({ titre, sous_titre, initial, catalogue, agent, envoi, onSave }) {
  const [valeurs, setValeurs] = useState(initial)
  const change = (champ, valeur) => setValeurs({ ...valeurs, [champ]: valeur })
  const desactivees = new Set(valeurs.fonctions_desactivees)
  const videDefaut = agent ? 'Comme son poste' : 'Défaut du socle'

  function basculer(code) {
    const suite = new Set(desactivees)
    if (suite.has(code)) suite.delete(code)
    else suite.add(code)
    change('fonctions_desactivees', [...suite])
  }

  return (
    <section className="card">
      <h2>{titre}</h2>
      {sous_titre && <p className="muted">{sous_titre}</p>}
      <div className="form-grid">
        <Niveau
          etiquette="Automatisation"
          valeur={valeurs.niveau_automatisation}
          options={catalogue.niveaux_automatisation}
          vide={videDefaut}
          onChange={(v) => change('niveau_automatisation', v)}
        />
        <Niveau
          etiquette="Gamification"
          valeur={valeurs.niveau_gamification}
          options={catalogue.niveaux_gamification}
          vide={videDefaut}
          onChange={(v) => change('niveau_gamification', v)}
        />
        {!agent && (
          <Niveau
            etiquette="Session la plus longue"
            valeur={valeurs.duree_session_max}
            options={catalogue.durees_session}
            vide="Plafond de la compagnie"
            onChange={(v) => change('duree_session_max', v)}
          />
        )}
        {agent && (
          <label>
            Aisance avec le numérique
            <select value={valeurs.aisance_numerique} onChange={(e) => change('aisance_numerique', e.target.value)}>
              {catalogue.aisances.map((a) => (
                <option key={a.valeur} value={a.valeur}>
                  {a.libelle}
                </option>
              ))}
            </select>
          </label>
        )}
        {agent ? (
          <label>
            Mode vocal
            <select
              value={valeurs.prefere_vocal === null ? '' : String(valeurs.prefere_vocal)}
              onChange={(e) => change('prefere_vocal', e.target.value === '' ? null : e.target.value === 'true')}
            >
              <option value="">Comme son poste</option>
              <option value="true">Préféré</option>
              <option value="false">Non</option>
            </select>
          </label>
        ) : (
          <label className="checkbox-ligne">
            <input type="checkbox" checked={valeurs.prefere_vocal} onChange={(e) => change('prefere_vocal', e.target.checked)} />
            Mode vocal préféré pour ce poste
          </label>
        )}
        <label className="checkbox-ligne">
          <input
            type="checkbox"
            checked={valeurs.prefere_vocal_impose}
            onChange={(e) => change('prefere_vocal_impose', e.target.checked)}
          />
          Imposer ce mode vocal ({agent ? "l'agent ne le choisit pas lui-même" : 'les agents du poste ne le choisissent pas eux-mêmes'})
        </label>
      </div>
      <fieldset className="fonctions">
        <legend>Fonctions retirées</legend>
        {catalogue.fonctions.map((f) => (
          <label key={f.code} className="checkbox-ligne">
            <input type="checkbox" checked={desactivees.has(f.code)} onChange={() => basculer(f.code)} />
            {f.libelle}
          </label>
        ))}
      </fieldset>
      <div className="button-row">
        <button type="button" disabled={envoi} onClick={() => onSave(valeurs)}>
          Enregistrer
        </button>
      </div>
    </section>
  )
}

export default function ConfigurationPage() {
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)

  const { data, error, loading, recharger } = useChargement(async () => {
    const [catalogue, postes, agents, cadre] = await Promise.all([
      apiFetch('/configuration/catalogue/'),
      apiFetch('/configuration/postes/'),
      apiFetch('/configuration/agents/'),
      apiFetch('/configuration/compagnie/'),
    ])
    return { catalogue, postes, agents, cadre }
  })

  async function enregistrer(requete, confirmation) {
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      await requete()
      await recharger()
      setMessage({ type: 'success', texte: confirmation })
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
    } finally {
      setEnvoi(false)
    }
  }

  if (!data) {
    return (
      <Layout title="Configuration">
        <Alert>{error}</Alert>
        {loading && <p>Chargement…</p>}
      </Layout>
    )
  }

  const { catalogue, postes, agents, cadre } = data

  return (
    <Layout title="Configuration">
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      <p className="muted">
        Vous réglez les postes placés directement sous votre autorité, dans le cadre fixé par la compagnie. Un réglage vide
        laisse le défaut : rien n&apos;est à configurer pour démarrer.
      </p>

      <h2 className="section-title">Cadre de la compagnie</h2>
      <section className="card">
        <p className="muted">
          Plafonds qu’aucun poste ne dépasse (fixés par le PDG) : automatisation « {cadre.automatisation_max} », gamification «{' '}
          {cadre.gamification_max} ».
        </p>
      </section>

      <h2 className="section-title">Postes</h2>
      {postes.length === 0 && <p>Aucun poste n&apos;est placé sous votre autorité.</p>}
      {postes.map((poste) => (
        <Reglage
          key={`${poste.role}-${poste.modifie_le}`}
          titre={poste.role_libelle}
          sous_titre={`Actuellement : automatisation ${poste.effectif.niveau_automatisation}, gamification ${poste.effectif.niveau_gamification}, session ${LABELS_DUREE_SESSION[poste.effectif.duree_session_max]?.toLowerCase()} au plus.`}
          initial={{
            niveau_automatisation: poste.niveau_automatisation,
            niveau_gamification: poste.niveau_gamification,
            prefere_vocal: poste.prefere_vocal,
            prefere_vocal_impose: poste.prefere_vocal_impose,
            fonctions_desactivees: poste.fonctions_desactivees,
            duree_session_max: poste.duree_session_max,
          }}
          catalogue={catalogue}
          envoi={envoi}
          onSave={(valeurs) =>
            enregistrer(
              () => apiFetch(`/configuration/postes/${poste.role}/`, { method: 'PUT', body: valeurs }),
              `Poste « ${poste.role_libelle} » enregistré.`,
            )
          }
        />
      ))}

      <h2 className="section-title">Agents</h2>
      <p className="muted">
        Ajustez un agent selon son aisance avec le numérique et sa préférence pour la voix : son réglage l&apos;emporte sur celui du poste.
      </p>
      {agents.length === 0 && <p>Aucun agent sous votre autorité.</p>}
      {agents.map((agent) => (
        <Reglage
          key={`${agent.agent}-${agent.modifie_le}`}
          agent
          titre={agent.agent_nom}
          sous_titre={agent.agent_role}
          initial={{
            niveau_automatisation: agent.niveau_automatisation,
            niveau_gamification: agent.niveau_gamification,
            prefere_vocal: agent.prefere_vocal,
            prefere_vocal_impose: agent.prefere_vocal_impose,
            fonctions_desactivees: agent.fonctions_desactivees,
            aisance_numerique: agent.aisance_numerique,
          }}
          catalogue={catalogue}
          envoi={envoi}
          onSave={(valeurs) =>
            enregistrer(
              () => apiFetch(`/configuration/agents/${agent.agent}/`, { method: 'PUT', body: valeurs }),
              `Réglage de ${agent.agent_nom} enregistré.`,
            )
          }
        />
      ))}
    </Layout>
  )
}
