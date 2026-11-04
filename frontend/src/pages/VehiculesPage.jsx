import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useActions from '../api/useActions.js'
import useChargement from '../api/useChargement.js'
import Alert from '../components/Alert.jsx'
import Badge from '../components/Badge.jsx'
import Layout from '../components/Layout.jsx'
import { LABELS_CLASSE_VEHICULE, LABELS_VEHICULE, TON_VEHICULE, etatEcheance, formatDate } from '../lib/format.js'

const VIDE = {
  immatriculation: '', capacite: '', marque: '', modele: '', annee_mise_en_circulation: '', classe: '', numero_carte_grise: '',
  carte_transport_numero: '', carte_transport_echeance: '', kilometrage: '',
}
const TEXTES = ['immatriculation', 'marque', 'modele', 'classe', 'numero_carte_grise', 'carte_transport_numero']

function valeursDe(vehicule) {
  if (!vehicule) return VIDE
  return Object.fromEntries(Object.keys(VIDE).map((champ) => [champ, vehicule[champ] === null ? '' : String(vehicule[champ])]))
}

/** Le formulaire d'un véhicule (`vehicule` absent : un nouveau véhicule, dont on peut saisir le kilométrage d'entrée). */
function FicheVehicule({ vehicule, onEnregistre, onSupprime }) {
  const [valeurs, setValeurs] = useState(() => valeursDe(vehicule))
  const { agir, envoi, message } = useActions(onEnregistre)
  const changer = (champ) => (event) => setValeurs({ ...valeurs, [champ]: event.target.value })
  const anneeMax = new Date().getFullYear() + 1

  async function supprimer() {
    // Un élément déjà utilisé (départs, tickets, historique) se garde : le serveur refuse et dit pourquoi.
    if (!window.confirm(`Retirer le véhicule ${vehicule.immatriculation} du parc ?`)) return
    await agir(() => apiFetch(`/vehicules/${vehicule.id}/`, { method: 'DELETE' }).then(() => onSupprime()), null)
  }

  async function enregistrer(event) {
    event.preventDefault()
    const corps = Object.fromEntries(TEXTES.map((champ) => [champ, valeurs[champ]]))
    corps.capacite = Number(valeurs.capacite)
    corps.annee_mise_en_circulation = valeurs.annee_mise_en_circulation === '' ? null : Number(valeurs.annee_mise_en_circulation)
    corps.carte_transport_echeance = valeurs.carte_transport_echeance || null
    if (!vehicule && valeurs.kilometrage !== '') corps.kilometrage = Number(valeurs.kilometrage)
    const ok = await agir(
      vehicule
        ? () => apiFetch(`/vehicules/${vehicule.id}/`, { method: 'PATCH', body: corps })
        : () => apiFetch('/vehicules/', { method: 'POST', body: corps }),
      vehicule ? `Fiche du véhicule ${valeurs.immatriculation} enregistrée.` : `Véhicule ${valeurs.immatriculation} ajouté au parc.`,
    )
    if (ok && !vehicule) setValeurs(VIDE)
  }

  return (
    <form onSubmit={enregistrer}>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      <div className="form-grid">
        <label>
          Immatriculation
          <input value={valeurs.immatriculation} onChange={changer('immatriculation')} maxLength={20} required />
        </label>
        <label>
          Places
          <input type="number" min="1" step="1" value={valeurs.capacite} onChange={changer('capacite')} required />
        </label>
        <label>
          Marque
          <input value={valeurs.marque} onChange={changer('marque')} maxLength={60} />
        </label>
        <label>
          Modèle
          <input value={valeurs.modele} onChange={changer('modele')} maxLength={60} />
        </label>
        <label>
          Mise en circulation (année)
          <input
            type="number"
            min="1950"
            max={anneeMax}
            step="1"
            value={valeurs.annee_mise_en_circulation}
            onChange={changer('annee_mise_en_circulation')}
          />
        </label>
        <label>
          Classe
          <select value={valeurs.classe} onChange={changer('classe')}>
            <option value="">— Non précisée —</option>
            {Object.entries(LABELS_CLASSE_VEHICULE).map(([valeur, libelle]) => (
              <option key={valeur} value={valeur}>
                {libelle}
              </option>
            ))}
          </select>
        </label>
        <label>
          N° de carte grise
          <input value={valeurs.numero_carte_grise} onChange={changer('numero_carte_grise')} maxLength={40} />
        </label>
        <label>
          N° de carte de transport
          <input value={valeurs.carte_transport_numero} onChange={changer('carte_transport_numero')} maxLength={40} />
        </label>
        <label>
          Échéance de la carte de transport
          <input type="date" value={valeurs.carte_transport_echeance} onChange={changer('carte_transport_echeance')} />
        </label>
        {!vehicule && (
          <label>
            Kilométrage à l&apos;entrée dans le parc
            <input type="number" min="0" step="1" value={valeurs.kilometrage} onChange={changer('kilometrage')} />
          </label>
        )}
      </div>
      {vehicule && valeurs.capacite !== '' && Number(valeurs.capacite) < vehicule.capacite && (
        <p className="muted">
          Moins de places : les billets déjà vendus sur les départs à venir de ce véhicule ne sont pas touchés, vérifiez-les.
        </p>
      )}
      <div className="fiche-actions">
        <button type="submit" disabled={envoi}>
          {vehicule ? 'Enregistrer la fiche' : 'Ajouter au parc'}
        </button>
        {vehicule && onSupprime && (
          <button type="button" className="button-secondary" disabled={envoi} onClick={supprimer}>
            Supprimer le véhicule
          </button>
        )}
      </div>
    </form>
  )
}

/**
 * Le parc de la compagnie, tenu sans l'administration : ajouter un véhicule, compléter sa fiche (marque, modèle, année de mise en
 * circulation, classe, carte grise, carte de transport). Le statut (disponible, en maintenance, bloqué sécurité) ne se change pas
 * d'ici : il suit les checklists, les blocages QHSE et l'atelier ; la gare d'attache se change par l'arbitrage du directeur des
 * opérations, et le kilométrage se relève avec l'entretien préventif.
 */
export default function VehiculesPage() {
  const [ouvert, setOuvert] = useState(null)
  const { data: vehicules, error, loading, recharger } = useChargement(() => apiFetch('/vehicules/'))

  if (!vehicules) {
    return (
      <Layout title="Véhicules">
        <Alert>{error}</Alert>
        {loading && <p>Chargement…</p>}
      </Layout>
    )
  }

  const vehicule = vehicules.find((v) => v.id === ouvert) || null
  const annee = new Date().getFullYear()

  return (
    <Layout title="Véhicules">
      <Alert>{error}</Alert>
      <section className="card">
        <h2>Parc ({vehicules.length} véhicules)</h2>
        {vehicules.length === 0 ? (
          <p className="muted">Aucun véhicule : ajoutez le premier ci-dessous.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Véhicule</th>
                  <th>Mise en circulation</th>
                  <th>Classe</th>
                  <th>Places</th>
                  <th>Gare d&apos;attache</th>
                  <th>Statut</th>
                  <th>Carte de transport</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {vehicules.map((v) => {
                  const carte = etatEcheance(v.carte_transport_echeance)
                  return (
                    <tr key={v.id}>
                      <td>
                        {v.immatriculation}
                        <div className="muted">{[v.marque, v.modele].filter(Boolean).join(' ') || '—'}</div>
                      </td>
                      <td>
                        {v.annee_mise_en_circulation ? (
                          <>
                            {v.annee_mise_en_circulation}
                            <div className="muted">{Math.max(0, annee - v.annee_mise_en_circulation)} an(s)</div>
                          </>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td>{LABELS_CLASSE_VEHICULE[v.classe] || '—'}</td>
                      <td>{v.capacite}</td>
                      <td>{v.gare_nom || <span className="muted">Non rattaché</span>}</td>
                      <td>
                        <Badge ton={TON_VEHICULE[v.statut]}>{LABELS_VEHICULE[v.statut] || v.statut}</Badge>
                      </td>
                      <td>
                        {carte ? (
                          <>
                            <Badge ton={carte.ton}>{carte.libelle}</Badge>
                            <div className="muted">{formatDate(v.carte_transport_echeance)}</div>
                          </>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td>
                        <button
                          type="button"
                          className="button-secondary button-small"
                          onClick={() => setOuvert(ouvert === v.id ? null : v.id)}
                        >
                          {ouvert === v.id ? 'Masquer' : 'Modifier'}
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {vehicule && (
        <section className="card card-highlight">
          <h2>Fiche du véhicule {vehicule.immatriculation}</h2>
          <FicheVehicule key={vehicule.id} vehicule={vehicule} onEnregistre={recharger} onSupprime={() => setOuvert(null)} />
        </section>
      )}

      <section className="card">
        <h2>Nouveau véhicule</h2>
        <FicheVehicule key="nouveau" onEnregistre={recharger} />
      </section>
    </Layout>
  )
}
