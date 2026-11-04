import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useActions from '../api/useActions.js'
import useChargement from '../api/useChargement.js'
import Alert from '../components/Alert.jsx'
import Badge from '../components/Badge.jsx'
import Layout from '../components/Layout.jsx'
import { formatDateHeure, formatFCFA } from '../lib/format.js'

const VIDE = { nom: '', reference: '', quantite_stock: '', seuil_alerte: '', prix_unitaire: '', fournisseur: '', emplacement: '' }
const TEXTES = ['nom', 'reference', 'fournisseur', 'emplacement']

/** Le formulaire d'une pièce (`piece` absente : une nouvelle pièce, dont on saisit le stock de départ). */
function FichePiece({ piece, onEnregistre, onSupprime }) {
  const [valeurs, setValeurs] = useState(() =>
    piece ? Object.fromEntries(Object.keys(VIDE).map((champ) => [champ, piece[champ] === null ? '' : String(piece[champ])])) : VIDE,
  )
  const { agir, envoi, message } = useActions(onEnregistre)
  const changer = (champ) => (event) => setValeurs({ ...valeurs, [champ]: event.target.value })

  async function enregistrer(event) {
    event.preventDefault()
    const corps = Object.fromEntries(TEXTES.map((champ) => [champ, valeurs[champ]]))
    corps.seuil_alerte = Number(valeurs.seuil_alerte || 0)
    corps.prix_unitaire = valeurs.prix_unitaire === '' ? null : valeurs.prix_unitaire
    if (!piece) corps.quantite_stock = Number(valeurs.quantite_stock || 0)
    const ok = await agir(
      piece
        ? () => apiFetch(`/pieces/${piece.id}/`, { method: 'PATCH', body: corps })
        : () => apiFetch('/pieces/', { method: 'POST', body: corps }),
      piece ? `Fiche de « ${valeurs.nom} » enregistrée.` : `Pièce « ${valeurs.nom} » ajoutée au catalogue.`,
    )
    if (ok && !piece) setValeurs(VIDE)
  }

  async function supprimer() {
    // Une pièce déjà reçue, sortie ou inventoriée garde son historique : le serveur refuse et dit pourquoi.
    if (!window.confirm(`Supprimer « ${piece.nom} » du catalogue ?`)) return
    await agir(() => apiFetch(`/pieces/${piece.id}/`, { method: 'DELETE' }).then(() => onSupprime?.()), null)
  }

  return (
    <form onSubmit={enregistrer}>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      <div className="form-grid">
        <label>
          Désignation
          <input value={valeurs.nom} onChange={changer('nom')} maxLength={255} required />
        </label>
        <label>
          Référence
          <input value={valeurs.reference} onChange={changer('reference')} maxLength={100} required />
        </label>
        {!piece && (
          <label>
            Stock de départ
            <input type="number" min="0" step="1" value={valeurs.quantite_stock} onChange={changer('quantite_stock')} />
          </label>
        )}
        <label>
          Seuil d&apos;alerte
          <input type="number" min="0" step="1" value={valeurs.seuil_alerte} onChange={changer('seuil_alerte')} />
        </label>
        <label>
          Prix unitaire (FCFA)
          <input type="number" min="0" step="1" value={valeurs.prix_unitaire} onChange={changer('prix_unitaire')} />
        </label>
        <label>
          Fournisseur habituel
          <input value={valeurs.fournisseur} onChange={changer('fournisseur')} maxLength={120} />
        </label>
        <label>
          Emplacement au magasin
          <input value={valeurs.emplacement} onChange={changer('emplacement')} maxLength={60} placeholder="Rayon B2" />
        </label>
      </div>
      {piece && (
        <p className="muted">
          Le stock bouge par les réceptions, les sorties et l&apos;inventaire ; le prix suit le coût moyen des réceptions.
        </p>
      )}
      <div className="fiche-actions">
        <button type="submit" disabled={envoi}>
          {piece ? 'Enregistrer la fiche' : 'Ajouter au catalogue'}
        </button>
        {piece && (
          <button type="button" className="button-secondary" disabled={envoi} onClick={supprimer}>
            Supprimer la pièce
          </button>
        )}
      </div>
    </form>
  )
}

function ChoixPiece({ pieces, valeur, onChange }) {
  return (
    <label>
      Pièce
      <select value={valeur} onChange={onChange} required>
        <option value="">— Choisir —</option>
        {pieces.map((p) => (
          <option key={p.id} value={p.id}>
            {p.nom} ({p.reference}) — {p.quantite_stock} en stock
          </option>
        ))}
      </select>
    </label>
  )
}

const RECEPTION_VIDE = { piece: '', quantite: '', prix_unitaire: '', fournisseur: '', reference_document: '' }

function Reception({ pieces, onEnregistre }) {
  const [valeurs, setValeurs] = useState(RECEPTION_VIDE)
  const { agir, envoi, message } = useActions(onEnregistre)
  const changer = (champ) => (event) => {
    const suivantes = { ...valeurs, [champ]: event.target.value }
    if (champ === 'piece' && !valeurs.fournisseur) {
      suivantes.fournisseur = pieces.find((p) => String(p.id) === event.target.value)?.fournisseur || ''
    }
    setValeurs(suivantes)
  }

  async function recevoir(event) {
    event.preventDefault()
    const piece = pieces.find((p) => String(p.id) === valeurs.piece)
    const corps = {
      ...valeurs,
      piece: Number(valeurs.piece),
      quantite: Number(valeurs.quantite),
      prix_unitaire: valeurs.prix_unitaire === '' ? null : valeurs.prix_unitaire,
    }
    const ok = await agir(
      () => apiFetch('/entrees-pieces/', { method: 'POST', body: corps }),
      `Réception enregistrée : ${corps.quantite} × ${piece?.nom}.`,
    )
    if (ok) setValeurs(RECEPTION_VIDE)
  }

  return (
    <section className="card">
      <h2>Réception</h2>
      <form onSubmit={recevoir}>
        <Alert type={message.type || 'error'}>{message.texte}</Alert>
        <div className="form-grid">
          <ChoixPiece pieces={pieces} valeur={valeurs.piece} onChange={changer('piece')} />
          <label>
            Quantité reçue
            <input type="number" min="1" step="1" value={valeurs.quantite} onChange={changer('quantite')} required />
          </label>
          <label>
            Prix unitaire payé (FCFA)
            <input type="number" min="0" step="1" value={valeurs.prix_unitaire} onChange={changer('prix_unitaire')} />
          </label>
          <label>
            Fournisseur
            <input value={valeurs.fournisseur} onChange={changer('fournisseur')} maxLength={120} />
          </label>
          <label>
            N° du bon de livraison ou de la facture
            <input value={valeurs.reference_document} onChange={changer('reference_document')} maxLength={60} />
          </label>
        </div>
        <div className="fiche-actions">
          <button type="submit" disabled={envoi}>
            Enregistrer la réception
          </button>
        </div>
      </form>
    </section>
  )
}

const INVENTAIRE_VIDE = { piece: '', quantite_comptee: '', motif: '' }

function Inventaire({ pieces, onEnregistre }) {
  const [valeurs, setValeurs] = useState(INVENTAIRE_VIDE)
  const { agir, envoi, message } = useActions(onEnregistre)
  const changer = (champ) => (event) => setValeurs({ ...valeurs, [champ]: event.target.value })
  const piece = pieces.find((p) => String(p.id) === valeurs.piece)
  const ecart = piece && valeurs.quantite_comptee !== '' ? Number(valeurs.quantite_comptee) - piece.quantite_stock : null

  async function compter(event) {
    event.preventDefault()
    const corps = { piece: Number(valeurs.piece), quantite_comptee: Number(valeurs.quantite_comptee), motif: valeurs.motif }
    const ok = await agir(
      () => apiFetch('/inventaires-pieces/', { method: 'POST', body: corps }),
      `Inventaire de « ${piece?.nom} » enregistré${ecart ? ` (écart ${ecart > 0 ? '+' : ''}${ecart})` : ', sans écart'}.`,
    )
    if (ok) setValeurs(INVENTAIRE_VIDE)
  }

  return (
    <section className="card">
      <h2>Inventaire</h2>
      <form onSubmit={compter}>
        <Alert type={message.type || 'error'}>{message.texte}</Alert>
        <div className="form-grid">
          <ChoixPiece pieces={pieces} valeur={valeurs.piece} onChange={changer('piece')} />
          <label>
            Quantité comptée
            <input type="number" min="0" step="1" value={valeurs.quantite_comptee} onChange={changer('quantite_comptee')} required />
          </label>
          <label>
            Motif de l&apos;écart
            <input value={valeurs.motif} onChange={changer('motif')} maxLength={255} required={Boolean(ecart)} />
          </label>
        </div>
        {ecart !== null && (
          <p className={ecart ? '' : 'muted'}>
            Attendu : {piece.quantite_stock} — écart : <strong>{ecart > 0 ? `+${ecart}` : ecart}</strong>
            {ecart < 0 && ' (le directeur technique sera prévenu)'}
          </p>
        )}
        <div className="fiche-actions">
          <button type="submit" disabled={envoi}>
            Enregistrer le comptage
          </button>
        </div>
      </form>
    </section>
  )
}

/** Corriger la quantité d'une sortie ou l'annuler : la différence revient au stock (si le règlement intérieur le permet). */
function CorrectionSortie({ sortie, agir, envoi }) {
  const [quantite, setQuantite] = useState(String(sortie.quantite))
  return (
    <div className="toolbar" style={{ margin: 0 }}>
      <input
        type="number"
        min="1"
        aria-label={`Quantité corrigée de la sortie ${sortie.id}`}
        value={quantite}
        onChange={(e) => setQuantite(e.target.value)}
        style={{ width: '5rem' }}
      />
      <button
        type="button"
        className="button-secondary button-small"
        disabled={envoi || !(Number(quantite) > 0) || Number(quantite) === sortie.quantite}
        onClick={() =>
          agir(
            () => apiFetch(`/sorties-pieces/${sortie.id}/`, { method: 'PATCH', body: { quantite: Number(quantite) } }),
            `Sortie corrigée : ${quantite} pièce(s), le stock est ajusté.`,
          )
        }
      >
        Corriger
      </button>
      <button
        type="button"
        className="button-secondary button-small"
        disabled={envoi}
        onClick={() => {
          if (!window.confirm(`Annuler cette sortie de ${sortie.quantite} pièce(s) ? Elles reviennent au stock.`)) return
          agir(() => apiFetch(`/sorties-pieces/${sortie.id}/`, { method: 'DELETE' }), 'Sortie annulée : les pièces sont revenues au stock.')
        }}
      >
        Annuler la sortie
      </button>
    </div>
  )
}

function Mouvements({ piece, corrigeable, agir, envoi }) {
  const { data, error } = useChargement(
    async () => {
      const [entrees, sorties, inventaires] = await Promise.all([
        apiFetch(`/entrees-pieces/?piece=${piece.id}`),
        apiFetch(`/sorties-pieces/?piece=${piece.id}`),
        apiFetch(`/inventaires-pieces/?piece=${piece.id}`),
      ])
      return [
        ...entrees.map((e) => ({
          cle: `e${e.id}`,
          date: e.date,
          libelle: 'Réception',
          quantite: `+${e.quantite}`,
          detail: [e.fournisseur, e.reference_document, e.prix_unitaire && formatFCFA(e.prix_unitaire), e.recue_par_nom]
            .filter(Boolean)
            .join(' · '),
        })),
        ...sorties.map((s) => ({
          cle: `s${s.id}`,
          date: s.date,
          libelle: 'Sortie',
          quantite: `−${s.quantite}`,
          detail: `Ordre de réparation n° ${s.ordre_reparation}`,
          sortie: s,
        })),
        ...inventaires.map((i) => ({
          cle: `i${i.id}`,
          date: i.date,
          libelle: 'Inventaire',
          quantite: i.ecart ? `${i.ecart > 0 ? '+' : ''}${i.ecart}` : '0',
          detail: `${i.quantite_comptee} compté(s), ${i.quantite_attendue} attendu(s)${i.motif ? ` · ${i.motif}` : ''} · ${i.compte_par_nom}`,
        })),
      ].sort((a, b) => b.date.localeCompare(a.date))
    },
    { cle: piece.id },
  )

  return (
    <>
      <Alert>{error}</Alert>
      {!data ? (
        <p>Chargement…</p>
      ) : data.length === 0 ? (
        <p className="muted">Aucun mouvement enregistré pour cette pièce.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Mouvement</th>
                <th>Quantité</th>
                <th>Détail</th>
              </tr>
            </thead>
            <tbody>
              {data.map((m) => (
                <tr key={m.cle}>
                  <td>{formatDateHeure(m.date)}</td>
                  <td>{m.libelle}</td>
                  <td>{m.quantite}</td>
                  <td>
                    {m.detail}
                    {corrigeable && m.sortie && <CorrectionSortie sortie={m.sortie} agir={agir} envoi={envoi} />}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

/**
 * Pièces et stock, pour le magasin et le technique : le catalogue (désignation, référence, prix, fournisseur, emplacement), les
 * réceptions qui font monter le stock, l'inventaire qui garde la trace de chaque écart, et l'historique des mouvements d'une pièce.
 */
export default function PiecesPage() {
  const [ouvert, setOuvert] = useState(null)
  const [vue, setVue] = useState('fiche')
  const { data: pieces, error, loading, recharger } = useChargement(() => apiFetch('/pieces/'))
  // Le règlement intérieur dit si le magasin et l'atelier corrigent ou annulent une sortie après coup.
  const { data: moi } = useChargement(() => apiFetch('/configuration/moi/'))
  // Tenue ici : le stock change après une correction, l'historique se relit, et la confirmation doit rester affichée.
  const sorties = useActions(recharger)

  if (!pieces) {
    return (
      <Layout title="Pièces et stock">
        <Alert>{error}</Alert>
        {loading && <p>Chargement…</p>}
      </Layout>
    )
  }

  const piece = pieces.find((p) => p.id === ouvert) || null
  const valeurTotale = pieces.reduce((total, p) => total + (p.valeur_stock === null ? 0 : Number(p.valeur_stock)), 0)
  const sansPrix = pieces.filter((p) => p.prix_unitaire === null).length
  const ouvrir = (id, quoi) => {
    setVue(quoi)
    setOuvert(ouvert === id && vue === quoi ? null : id)
  }

  return (
    <Layout title="Pièces et stock">
      <Alert>{error}</Alert>
      <section className="card">
        <h2>Catalogue ({pieces.length} pièces)</h2>
        <p className="muted">
          Valeur du stock : <strong>{formatFCFA(valeurTotale)}</strong>
          {sansPrix > 0 && ` (${sansPrix} pièce(s) sans prix, non comptée(s))`}.
        </p>
        {pieces.length === 0 ? (
          <p className="muted">Aucune pièce : ajoutez la première ci-dessous.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Pièce</th>
                  <th>Emplacement</th>
                  <th>Fournisseur</th>
                  <th>Stock</th>
                  <th>Seuil</th>
                  <th>Prix unitaire</th>
                  <th>Valeur</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {pieces.map((p) => (
                  <tr key={p.id}>
                    <td>
                      {p.nom}
                      <div className="muted">{p.reference}</div>
                    </td>
                    <td>{p.emplacement || '—'}</td>
                    <td>{p.fournisseur || '—'}</td>
                    <td>
                      {p.en_alerte ? <Badge ton={p.quantite_stock === 0 ? 'rouge' : 'orange'}>{p.quantite_stock}</Badge> : p.quantite_stock}
                    </td>
                    <td>{p.seuil_alerte}</td>
                    <td>{p.prix_unitaire === null ? '—' : formatFCFA(p.prix_unitaire)}</td>
                    <td>{p.valeur_stock === null ? '—' : formatFCFA(p.valeur_stock)}</td>
                    <td>
                      <div className="button-row">
                        <button type="button" className="button-secondary button-small" onClick={() => ouvrir(p.id, 'fiche')}>
                          {ouvert === p.id && vue === 'fiche' ? 'Masquer' : 'Modifier'}
                        </button>
                        <button type="button" className="button-secondary button-small" onClick={() => ouvrir(p.id, 'mouvements')}>
                          {ouvert === p.id && vue === 'mouvements' ? 'Masquer' : 'Mouvements'}
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

      {piece && (
        <section className="card card-highlight">
          <h2>
            {vue === 'fiche' ? 'Fiche de' : 'Mouvements de'} {piece.nom}
          </h2>
          {vue === 'fiche' ? (
            <FichePiece
              key={piece.id}
              piece={piece}
              onEnregistre={recharger}
              onSupprime={() => {
                setOuvert(null)
                return recharger()
              }}
            />
          ) : (
            <>
              <Alert type={sorties.message.type || 'error'}>{sorties.message.texte}</Alert>
              {/* Relu après chaque mouvement (le stock de la pièce change). */}
              <Mouvements
                key={`${piece.id}-${piece.quantite_stock}-${piece.prix_unitaire}`}
                piece={piece}
                corrigeable={Boolean(moi?.reglement?.sorties_pieces_corrigeables)}
                agir={sorties.agir}
                envoi={sorties.envoi}
              />
            </>
          )}
        </section>
      )}

      <Reception pieces={pieces} onEnregistre={recharger} />
      <Inventaire pieces={pieces} onEnregistre={recharger} />

      <section className="card">
        <h2>Nouvelle pièce</h2>
        <FichePiece key="nouvelle" onEnregistre={recharger} />
      </section>
    </Layout>
  )
}
