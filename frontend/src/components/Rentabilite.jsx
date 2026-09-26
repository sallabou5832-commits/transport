import { useState } from 'react'
import { apiFetch, apiTelecharger } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Kpi from './Kpi.jsx'
import { formatDate, formatFCFA, isoAujourdhui } from '../lib/format.js'
import { CATEGORIES_DEPENSE, dernierJourDuMois, premierJourDuMois } from '../lib/finance.js'

const PERIODES = [
  { id: 'mois', label: 'Ce mois', debut: () => premierJourDuMois(0), fin: () => isoAujourdhui(0) },
  { id: 'precedent', label: 'Mois dernier', debut: () => premierJourDuMois(-1), fin: () => dernierJourDuMois(-1) },
  { id: '30j', label: '30 derniers jours', debut: () => isoAujourdhui(-29), fin: () => isoAujourdhui(0) },
  { id: 'perso', label: 'Période personnalisée' },
]

const taux = (valeur) => (valeur === null ? '—' : `${valeur} %`)
const detailCategories = (categories) =>
  Object.entries(categories)
    .map(([categorie, montant]) => `${(CATEGORIES_DEPENSE[categorie] || categorie).toLowerCase()} ${formatFCFA(montant)}`)
    .join(', ')

/**
 * Rentabilité par ligne et par gare : les recettes (billets et fret) contre les dépenses de la période, classées par marge. Les
 * charges sans ligne ni gare (salaires, frais généraux) pèsent sur le total. Export CSV (Excel) et impression (PDF) du même état.
 * `version` la recalcule après une saisie faite ailleurs sur la page.
 */
export default function Rentabilite({ version = 0 }) {
  const [periode, setPeriode] = useState('mois')
  const [debutPerso, setDebutPerso] = useState(isoAujourdhui(-29))
  const [finPerso, setFinPerso] = useState(isoAujourdhui(0))
  const [erreurExport, setErreurExport] = useState('')

  const choix = PERIODES.find((p) => p.id === periode)
  const debut = choix.debut ? choix.debut() : debutPerso
  const fin = choix.fin ? choix.fin() : finPerso

  const { data, error } = useChargement(
    async () => {
      if (!debut || !fin) throw new Error('Choisissez une date de début et une date de fin.')
      if (debut > fin) throw new Error('La date de début doit précéder la date de fin.')
      return apiFetch(`/finance/rentabilite/?date_debut=${debut}&date_fin=${fin}`)
    },
    { cle: `${debut}|${fin}|${version}` },
  )

  async function exporter() {
    setErreurExport('')
    try {
      await apiTelecharger(`/finance/export/?type=rentabilite&date_debut=${debut}&date_fin=${fin}`, `rentabilite-${debut}-${fin}.csv`)
    } catch (err) {
      setErreurExport(err.message)
    }
  }

  return (
    <section className="card imprimable">
      <h2>Rentabilité par ligne et par gare</h2>
      <div className="toolbar no-print">
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
        {periode === 'perso' && (
          <>
            <label>
              Du
              <input type="date" value={debutPerso} onChange={(e) => setDebutPerso(e.target.value)} />
            </label>
            <label>
              Au
              <input type="date" value={finPerso} onChange={(e) => setFinPerso(e.target.value)} />
            </label>
          </>
        )}
        <button type="button" className="button-secondary" disabled={!data} onClick={exporter}>
          Exporter (Excel / CSV)
        </button>
        <button type="button" className="button-secondary" disabled={!data} onClick={() => window.print()}>
          Imprimer / PDF
        </button>
      </div>
      <Alert>{error || erreurExport}</Alert>

      {data && (
        <>
          <p className="muted">
            Du {formatDate(data.periode.debut)} au {formatDate(data.periode.fin)}.
          </p>
          <div className="cards-grid">
            <Kpi titre="Recettes" valeur={formatFCFA(data.total.recettes)} ton="vert" detail="billets et fret" />
            <Kpi titre="Dépenses" valeur={formatFCFA(data.total.depenses)} detail={`dont ${formatFCFA(data.charges_communes)} de charges communes`} />
            <Kpi
              titre="Marge"
              valeur={formatFCFA(data.total.marge)}
              ton={Number(data.total.marge) < 0 ? 'rouge' : 'vert'}
              detail={`taux de marge : ${taux(data.total.taux_marge_pourcent)}`}
            />
          </div>

          <h3>Par ligne</h3>
          {data.lignes.length === 0 ? (
            <p className="muted">Aucune recette ni dépense de ligne sur cette période.</p>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Ligne</th>
                    <th>Recettes</th>
                    <th>Dépenses</th>
                    <th>Marge</th>
                    <th>Taux</th>
                  </tr>
                </thead>
                <tbody>
                  {data.lignes.map((ligne) => (
                    <tr key={ligne.id} className={Number(ligne.marge) < 0 ? 'row-danger' : ''}>
                      <td>
                        {ligne.nom}
                        <div className="muted">départ {ligne.gare}</div>
                      </td>
                      <td>
                        {formatFCFA(ligne.recettes)}
                        <div className="muted">
                          billets {formatFCFA(ligne.billets)} · fret {formatFCFA(ligne.fret)}
                        </div>
                      </td>
                      <td>
                        {formatFCFA(ligne.depenses)}
                        {Object.keys(ligne.depenses_par_categorie).length > 0 && (
                          <div className="muted">{detailCategories(ligne.depenses_par_categorie)}</div>
                        )}
                      </td>
                      <td className="montant">
                        <strong>{formatFCFA(ligne.marge)}</strong>
                      </td>
                      <td>{taux(ligne.taux_marge_pourcent)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <h3>Par gare de départ</h3>
          {data.gares.length === 0 ? (
            <p className="muted">Aucune recette ni dépense de gare sur cette période.</p>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Gare</th>
                    <th>Recettes</th>
                    <th>Dépenses</th>
                    <th>Marge</th>
                    <th>Taux</th>
                  </tr>
                </thead>
                <tbody>
                  {data.gares.map((gare) => (
                    <tr key={gare.id} className={Number(gare.marge) < 0 ? 'row-danger' : ''}>
                      <td>{gare.nom}</td>
                      <td className="montant">{formatFCFA(gare.recettes)}</td>
                      <td className="montant">{formatFCFA(gare.depenses)}</td>
                      <td className="montant">
                        <strong>{formatFCFA(gare.marge)}</strong>
                      </td>
                      <td>{taux(gare.taux_marge_pourcent)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  )
}
