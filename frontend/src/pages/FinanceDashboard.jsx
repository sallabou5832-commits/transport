import { useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'
import Kpi from '../components/Kpi.jsx'
import Barres from '../components/Barres.jsx'
import Tresorerie from '../components/Tresorerie.jsx'
import { formatDate, formatFCFA, isoAujourdhui } from '../lib/format.js'

const PERIODES = [
  { id: 'jour', label: "Aujourd'hui", jours: 0 },
  { id: '7j', label: '7 derniers jours', jours: 6 },
  { id: '30j', label: '30 derniers jours', jours: 29 },
  { id: 'perso', label: 'Période personnalisée' },
]

const LABELS_MODE = { especes: 'Espèces', mobile_money: 'Mobile money' }

function exporterCsv(donnees) {
  const lignes = [['Section', 'Libellé', 'Tickets', 'Montant (FCFA)']]
  donnees.gares.forEach((g) => lignes.push(['Gare', g.gare_nom, g.nombre_tickets, Number(g.montant_total)]))
  donnees.par_mode_paiement.forEach((m) =>
    lignes.push(['Mode de paiement', LABELS_MODE[m.mode] || m.mode, m.nombre_tickets, Number(m.montant_total)]),
  )
  donnees.par_jour.forEach((j) => lignes.push(['Jour', j.date, j.nombre_tickets, Number(j.montant_total)]))
  lignes.push(['Total billets', '', donnees.total.nombre_tickets, Number(donnees.total.montant_total)])
  donnees.fret.par_mode_paiement.forEach((m) =>
    lignes.push(['Fret (colis et bagages)', LABELS_MODE[m.mode] || m.mode, m.nombre_colis, Number(m.montant_total)]),
  )
  lignes.push(['Total fret', '', donnees.fret.nombre_colis, Number(donnees.fret.montant_total)])
  lignes.push(['Total général (billets + fret)', '', '', Number(donnees.total_general.montant_total)])

  // Séparateur « ; » et BOM UTF-8 : Excel en français ouvre alors le fichier directement, accents compris.
  const contenu =
    '﻿' + lignes.map((l) => l.map((c) => `"${String(c).replaceAll('"', '""')}"`).join(';')).join('\r\n')
  const url = URL.createObjectURL(new Blob([contenu], { type: 'text/csv;charset=utf-8' }))
  const lien = document.createElement('a')
  lien.href = url
  lien.download = `recettes_${donnees.date_debut}_${donnees.date_fin}.csv`
  lien.click()
  URL.revokeObjectURL(url)
}

export default function FinanceDashboard() {
  const [periode, setPeriode] = useState('7j')
  const [debutPerso, setDebutPerso] = useState(isoAujourdhui(-6))
  const [finPerso, setFinPerso] = useState(isoAujourdhui(0))

  const choix = PERIODES.find((p) => p.id === periode)
  const debut = choix.jours === undefined ? debutPerso : isoAujourdhui(-choix.jours)
  const fin = choix.jours === undefined ? finPerso : isoAujourdhui(0)

  const { data, error, loading } = useChargement(
    async () => {
      if (!debut || !fin) throw new Error('Choisissez une date de début et une date de fin.')
      if (debut > fin) throw new Error('La date de début doit précéder la date de fin.')
      return apiFetch(`/synthese-financiere/?date_debut=${debut}&date_fin=${fin}`)
    },
    { cle: `${debut}|${fin}` },
  )

  const total = data ? Number(data.total.montant_total) : 0
  const nombre = data ? data.total.nombre_tickets : 0
  const mobile = data ? data.par_mode_paiement.find((m) => m.mode === 'mobile_money') : null
  const partMobile = total > 0 && mobile ? Math.round((Number(mobile.montant_total) / total) * 100) : 0

  return (
    <Layout title="Tableau de bord — Finance">
      <h2 className="section-title">Trésorerie</h2>
      <Tresorerie />
      <p className="muted">
        Dépenses, budgets carburant, rentabilité par ligne et paiements aux fournisseurs : page{' '}
        <Link to="/comptabilite">Comptabilité</Link>.
      </p>

      <h2 className="section-title">Recettes</h2>
      <div className="toolbar">
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
        <button type="button" disabled={!data} onClick={() => exporterCsv(data)}>
          Exporter (Excel / CSV)
        </button>
      </div>

      <Alert>{error}</Alert>
      {loading && !data && <p>Chargement…</p>}

      {data && (
        <>
          <p className="muted">
            Recettes du {formatDate(data.date_debut)} au {formatDate(data.date_fin)}, consolidées pour toutes les
            gares.
          </p>
          <div className="cards-grid">
            <Kpi titre="Recettes de billetterie" valeur={formatFCFA(total)} ton="vert" />
            <Kpi
              titre="Fret encaissé (colis et bagages)"
              valeur={formatFCFA(data.fret.montant_total)}
              detail={`${data.fret.nombre_colis} colis`}
            />
            <Kpi titre="Total encaissé" valeur={formatFCFA(data.total_general.montant_total)} ton="vert" />
            <Kpi titre="Tickets vendus" valeur={nombre.toLocaleString('fr-FR')} />
            <Kpi titre="Panier moyen" valeur={formatFCFA(nombre > 0 ? total / nombre : 0)} />
            <Kpi titre="Part du mobile money" valeur={`${partMobile} %`} />
          </div>

          <h2 className="section-title">Mode d&apos;encaissement</h2>
          <section className="card">
            <Barres
              lignes={data.par_mode_paiement.map((m) => ({
                cle: m.mode,
                label: LABELS_MODE[m.mode] || m.mode,
                valeur: Number(m.montant_total),
              }))}
              format={formatFCFA}
            />
          </section>

          <h2 className="section-title">Recettes par gare de départ</h2>
          <section className="card">
            <Barres
              lignes={[...data.gares]
                .sort((a, b) => Number(b.montant_total) - Number(a.montant_total))
                .map((g) => ({ cle: g.gare_id, label: g.gare_nom, valeur: Number(g.montant_total) }))}
              format={formatFCFA}
              vide="Aucune vente sur cette période."
            />
          </section>

          <h2 className="section-title">Évolution jour par jour</h2>
          <section className="card">
            <Barres
              lignes={data.par_jour.map((j) => ({
                cle: j.date,
                label: formatDate(j.date),
                valeur: Number(j.montant_total),
              }))}
              format={formatFCFA}
              vide="Aucune vente sur cette période."
            />
          </section>
        </>
      )}
    </Layout>
  )
}
