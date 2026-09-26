import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import { formatDateHeure, formatFCFA } from '../lib/format.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'

const EXPLICATION_NIVEAU = {
  manuel: 'Niveau manuel : remettez votre caisse à votre chef de gare, qui la clôture.',
  automatique: 'Niveau automatique : votre caisse est clôturée toute seule en fin de journée ; vérifiez-la ici.',
}

/**
 * Caisse du jour : les totaux en direct et la clôture (photo figée transmise au chef de gare). `equipe` : vue du chef de
 * gare (un bloc par guichetier, avec le bouton de clôture pour ceux qui ne l'ont pas encore faite) ; sinon, la caisse du
 * guichetier connecté, qu'il clôture d'un geste selon son niveau d'automatisation.
 */
export default function CaissesDuJour({ equipe = false, apresAction }) {
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)
  const { data, error, recharger } = useChargement(() => apiFetch('/clotures-caisse/etat/'), { intervalleMs: 60000 })

  async function cloturer(ligne) {
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      await apiFetch('/clotures-caisse/', { method: 'POST', body: equipe ? { guichetier: ligne.guichetier } : {} })
      await recharger()
      apresAction?.()
      setMessage({ type: 'success', texte: `Caisse de ${ligne.guichetier_nom} clôturée : le chef de gare en est prévenu.` })
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
    } finally {
      setEnvoi(false)
    }
  }

  if (!data) return <Alert>{error}</Alert>
  if (data.length === 0) return <p>{equipe ? 'Aucun guichetier n’est affecté à votre gare.' : 'Aucune caisse.'}</p>

  return (
    <>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      <div className="cards-grid">
        {data.map((ligne) => {
          const { caisse, cloture } = ligne
          return (
            <section className="card" key={ligne.guichetier}>
              <h2>{equipe ? ligne.guichetier_nom : 'Ma caisse du jour'}</h2>
              <p className="big-number">{formatFCFA(cloture ? cloture.montant_total : caisse.montant_total)}</p>
              <p className="muted">
                {caisse.nombre_tickets} ticket(s) · espèces {formatFCFA(caisse.especes.montant)} · mobile money{' '}
                {formatFCFA(caisse.mobile_money.montant)}
                {caisse.annulations.nombre > 0 && ` · ${caisse.annulations.nombre} annulation(s) à rendre`}
              </p>
              {cloture ? (
                <p>
                  <Badge ton="vert">Clôturée</Badge>{' '}
                  <span className="muted">
                    {formatDateHeure(cloture.cloture_le)} — {cloture.cloture_par_nom || 'automatique'}
                  </span>
                </p>
              ) : (
                <>
                  {!equipe && EXPLICATION_NIVEAU[ligne.niveau_automatisation] && (
                    <p className="muted">{EXPLICATION_NIVEAU[ligne.niveau_automatisation]}</p>
                  )}
                  {(equipe || ligne.niveau_automatisation === 'assiste') && (
                    <button type="button" className="button-small" disabled={envoi} onClick={() => cloturer(ligne)}>
                      {equipe ? 'Clôturer sa caisse' : 'Clôturer ma caisse'}
                    </button>
                  )}
                </>
              )}
            </section>
          )
        })}
      </div>
    </>
  )
}
