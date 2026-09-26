import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'
import Badge from '../components/Badge.jsx'
import { LABELS_DEPART, estAujourdhui, formatDateHeure, formatFCFA, formatHeure, indexParId } from '../lib/format.js'

const STATUTS = {
  enregistre: { label: 'Enregistré', ton: 'orange' },
  charge: { label: 'En route', ton: 'bleu' },
  arrive: { label: 'Arrivé', ton: 'vert' },
  retire: { label: 'Retiré', ton: 'neutre' },
  annule: { label: 'Annulé', ton: 'rouge' },
}

const VIDE = {
  depart: '',
  type_colis: 'colis',
  description: '',
  poids_kg: '',
  valeur_declaree: '',
  frais: '',
  mode_paiement: 'especes',
  ticket: '',
  expediteur_nom: '',
  expediteur_telephone: '',
  destinataire_nom: '',
  destinataire_telephone: '',
}

export default function BagagisteDashboard() {
  const [form, setForm] = useState(VIDE)
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)
  const [departPlan, setDepartPlan] = useState('')
  const [retraits, setRetraits] = useState({})

  const { data, error, loading, recharger } = useChargement(
    async () => {
      const [departs, lignes, colis, tickets] = await Promise.all([
        apiFetch('/departs/'),
        apiFetch('/lignes/'),
        apiFetch('/colis/'),
        apiFetch('/tickets/'),
      ])
      return { departs, lignes, colis, tickets }
    },
    { intervalleMs: 60000 },
  )

  // Le plan de chargement du départ choisi, rechargé quand il change ou après une action.
  const plan = useChargement(
    async () => (departPlan ? apiFetch(`/departs/${departPlan}/plan-chargement/`) : null),
    { cle: `${departPlan}|${data?.colis.length}|${data?.colis.filter((c) => c.statut === 'charge').length}` },
  )

  async function agir(requete, confirmation) {
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      await requete()
      // Les listes d'abord, le message ensuite : on n'annonce pas « chargé » devant un colis encore listé « à charger ».
      await recharger()
      await plan.recharger()
      setMessage({ type: 'success', texte: confirmation })
      return true
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
      return false
    } finally {
      setEnvoi(false)
    }
  }

  async function enregistrer(event) {
    event.preventDefault()
    const corps = {
      depart: Number(form.depart),
      type_colis: form.type_colis,
      description: form.description,
      poids_kg: form.poids_kg,
      valeur_declaree: form.valeur_declaree || '0',
      frais: form.frais || '0',
      expediteur_nom: form.expediteur_nom,
      expediteur_telephone: form.expediteur_telephone,
      destinataire_nom: form.destinataire_nom,
      destinataire_telephone: form.destinataire_telephone,
    }
    if (Number(corps.frais) > 0) corps.mode_paiement = form.mode_paiement
    if (form.ticket) corps.ticket = Number(form.ticket)
    // Bagage d'un voyageur : ses coordonnées viennent de son billet, on n'envoie que ce qui a été saisi.
    for (const champ of ['expediteur_nom', 'expediteur_telephone', 'destinataire_nom', 'destinataire_telephone']) {
      if (form.ticket && !corps[champ]) delete corps[champ]
    }
    const ok = await agir(
      () => apiFetch('/colis/', { method: 'POST', body: corps }),
      'Colis enregistré : le code de retrait a été envoyé au destinataire par SMS et WhatsApp.',
    )
    if (ok) {
      setDepartPlan(form.depart)
      setForm({ ...VIDE, depart: form.depart })
    }
  }

  if (!data) {
    return (
      <Layout title="Tableau de bord — Bagagiste">
        <Alert>{error}</Alert>
        {loading && <p>Chargement…</p>}
      </Layout>
    )
  }

  const { departs, lignes, colis, tickets } = data
  const lignesParId = indexParId(lignes)
  const departsParId = indexParId(departs)
  const aVenir = departs
    .filter((d) => d.statut === 'planifie' && estAujourdhui(d.date_heure))
    .sort((a, b) => new Date(a.date_heure) - new Date(b.date_heure))
  const libelleDepart = (d) => `${lignesParId[d.ligne]?.nom} — ${formatHeure(d.date_heure)} (${LABELS_DEPART[d.statut]})`
  const billets = tickets.filter((t) => String(t.depart) === form.depart && t.statut === 'valide')

  const parStatut = (statut) => colis.filter((c) => c.statut === statut)
  const aCharger = parStatut('enregistre')
  const enRoute = parStatut('charge')
  const aRetirer = parStatut('arrive')
  const historique = colis.filter((c) => c.statut === 'retire' || c.statut === 'annule').slice(0, 8)

  return (
    <Layout title="Tableau de bord — Bagagiste">
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>

      <div className="cards-grid">
        <section className="card kpi">
          <h2>À charger</h2>
          <p className="big-number">{aCharger.length}</p>
        </section>
        <section className="card kpi">
          <h2>En route</h2>
          <p className="big-number">{enRoute.length}</p>
        </section>
        <section className="card kpi kpi-vert">
          <h2>À remettre au client</h2>
          <p className="big-number">{aRetirer.length}</p>
        </section>
      </div>

      <h2 className="section-title">Enregistrer un bagage ou un colis</h2>
      <section className="card">
        <form onSubmit={enregistrer}>
          <div className="form-grid">
            <label>
              Départ
              <select value={form.depart} onChange={(e) => setForm({ ...form, depart: e.target.value, ticket: '' })} required>
                <option value="">— Choisir un départ —</option>
                {aVenir.map((d) => (
                  <option key={d.id} value={d.id}>
                    {libelleDepart(d)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Nature
              <select value={form.type_colis} onChange={(e) => setForm({ ...form, type_colis: e.target.value })}>
                <option value="colis">Colis (envoi seul)</option>
                <option value="bagage">Bagage d’un voyageur</option>
              </select>
            </label>
            <label>
              Billet du voyageur (facultatif)
              <select value={form.ticket} onChange={(e) => setForm({ ...form, ticket: e.target.value })} disabled={!form.depart}>
                <option value="">— Aucun —</option>
                {billets.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.passager_nom} ({t.passager_telephone})
                  </option>
                ))}
              </select>
            </label>
            <label>
              Description
              <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} required />
            </label>
            <label>
              Poids estimé (kg)
              <input type="number" min="0.1" step="0.1" value={form.poids_kg} onChange={(e) => setForm({ ...form, poids_kg: e.target.value })} required />
            </label>
            <label>
              Valeur déclarée (FCFA)
              <input type="number" min="0" step="1" value={form.valeur_declaree} onChange={(e) => setForm({ ...form, valeur_declaree: e.target.value })} />
            </label>
            <label>
              Frais de fret (FCFA)
              <input type="number" min="0" step="1" value={form.frais} onChange={(e) => setForm({ ...form, frais: e.target.value })} />
            </label>
            <label>
              Paiement des frais
              <select value={form.mode_paiement} onChange={(e) => setForm({ ...form, mode_paiement: e.target.value })}>
                <option value="especes">Espèces</option>
                <option value="mobile_money">Mobile money</option>
              </select>
            </label>
            <label>
              Expéditeur
              <input value={form.expediteur_nom} onChange={(e) => setForm({ ...form, expediteur_nom: e.target.value })} required={!form.ticket} />
            </label>
            <label>
              Téléphone de l’expéditeur
              <input type="tel" value={form.expediteur_telephone} onChange={(e) => setForm({ ...form, expediteur_telephone: e.target.value })} />
            </label>
            <label>
              Destinataire
              <input value={form.destinataire_nom} onChange={(e) => setForm({ ...form, destinataire_nom: e.target.value })} required={!form.ticket} />
            </label>
            <label>
              Téléphone du destinataire (reçoit le code de retrait)
              <input type="tel" value={form.destinataire_telephone} onChange={(e) => setForm({ ...form, destinataire_telephone: e.target.value })} required={!form.ticket} />
            </label>
          </div>
          <div className="button-row">
            <button type="submit" disabled={envoi}>
              Enregistrer et envoyer le code
            </button>
          </div>
        </form>
      </section>

      <h2 className="section-title">Aide au chargement</h2>
      <div className="toolbar">
        <label>
          Départ
          <select value={departPlan} onChange={(e) => setDepartPlan(e.target.value)}>
            <option value="">— Choisir un départ —</option>
            {aVenir.map((d) => (
              <option key={d.id} value={d.id}>
                {libelleDepart(d)}
              </option>
            ))}
          </select>
        </label>
      </div>
      {plan.data && (
        <section className="card">
          {plan.data.depasse && (
            <Alert type="warning">
              Charge de {Math.round(plan.data.poids_total_kg)} kg : au-dessus de la limite de soute ({Math.round(plan.data.charge_max_kg)} kg).
            </Alert>
          )}
          <p className="muted">
            Poids total {Math.round(plan.data.poids_total_kg)} kg · écart entre zones {Math.round(plan.data.ecart_max_kg)} kg. Chargez les plus
            lourds d’abord, chacun dans la zone indiquée.
          </p>
          <div className="cards-grid">
            {plan.data.zones.map((zone) => (
              <div key={zone.nom} className="card">
                <h2>
                  <span style={{ textTransform: 'capitalize' }}>{zone.nom}</span> · {Math.round(zone.poids_kg)} kg
                </h2>
                {zone.colis.length === 0 ? (
                  <p className="muted">Vide</p>
                ) : (
                  <ul className="stat-list">
                    {zone.colis.map((c) => (
                      <li key={c.id}>
                        <span>
                          {c.reference} — {c.description}
                        </span>
                        <strong>{Math.round(c.poids_kg)} kg</strong>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      <h2 className="section-title">Colis à charger</h2>
      {aCharger.length === 0 ? (
        <p>Aucun colis en attente de chargement.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Référence</th>
                <th>Description</th>
                <th>Poids</th>
                <th>Départ</th>
                <th>Destinataire</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {aCharger.map((c) => (
                <tr key={c.id}>
                  <td>{c.reference}</td>
                  <td>{c.description}</td>
                  <td>{Math.round(c.poids_kg)} kg</td>
                  <td>{c.depart_libelle}</td>
                  <td>{c.destinataire_nom}</td>
                  <td>
                    <button
                      type="button"
                      className="button-small"
                      disabled={envoi || departsParId[c.depart]?.statut !== 'planifie'}
                      onClick={() => agir(() => apiFetch(`/colis/${c.id}/charger/`, { method: 'POST' }), `${c.reference} chargé.`)}
                    >
                      Marquer chargé
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2 className="section-title">Colis à remettre (arrivés dans votre gare)</h2>
      {aRetirer.length === 0 ? (
        <p>Aucun colis à remettre.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Référence</th>
                <th>Description</th>
                <th>Destinataire</th>
                <th>Remise</th>
              </tr>
            </thead>
            <tbody>
              {aRetirer.map((c) => {
                const saisie = retraits[c.id] || { code: '', nom: '' }
                return (
                  <tr key={c.id}>
                    <td>{c.reference}</td>
                    <td>{c.description}</td>
                    <td>
                      {c.destinataire_nom}
                      <br />
                      <span className="muted">{c.destinataire_telephone}</span>
                    </td>
                    <td>
                      {c.code_verrouille ? (
                        <Badge ton="rouge">Verrouillé : demandez un nouveau code à votre chef de gare</Badge>
                      ) : (
                        <div className="toolbar" style={{ margin: 0 }}>
                          <input
                            placeholder="Code du client"
                            aria-label={`Code de retrait de ${c.reference}`}
                            value={saisie.code}
                            onChange={(e) => setRetraits({ ...retraits, [c.id]: { ...saisie, code: e.target.value } })}
                            style={{ width: '8rem' }}
                          />
                          <input
                            placeholder="Nom de la personne"
                            aria-label={`Nom de la personne qui retire ${c.reference}`}
                            value={saisie.nom}
                            onChange={(e) => setRetraits({ ...retraits, [c.id]: { ...saisie, nom: e.target.value } })}
                          />
                          <button
                            type="button"
                            className="button-small"
                            disabled={envoi || !saisie.code.trim()}
                            onClick={() =>
                              agir(
                                () => apiFetch(`/colis/${c.id}/retirer/`, { method: 'POST', body: { code: saisie.code, retire_par_nom: saisie.nom } }),
                                `${c.reference} remis.`,
                              )
                            }
                          >
                            Remettre
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {enRoute.length > 0 && (
        <>
          <h2 className="section-title">Colis en route</h2>
          <ul className="stat-list">
            {enRoute.map((c) => (
              <li key={c.id}>
                <span>
                  {c.reference} — {c.description} → {c.gare_arrivee_nom}
                </span>
                <span className="muted">{c.depart_libelle}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      {historique.length > 0 && (
        <>
          <h2 className="section-title">Derniers colis clôturés</h2>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Référence</th>
                  <th>Description</th>
                  <th>Statut</th>
                  <th>Frais</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {historique.map((c) => (
                  <tr key={c.id}>
                    <td>{c.reference}</td>
                    <td>{c.description}</td>
                    <td>
                      <Badge ton={STATUTS[c.statut].ton}>{STATUTS[c.statut].label}</Badge>
                      {c.statut === 'retire' && c.retire_par_nom && <span className="muted"> par {c.retire_par_nom}</span>}
                    </td>
                    <td>{formatFCFA(c.frais)}</td>
                    <td>{formatDateHeure(c.retire_le || c.annule_le)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Layout>
  )
}
