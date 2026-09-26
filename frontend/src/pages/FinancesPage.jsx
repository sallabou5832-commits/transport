import Layout from '../components/Layout.jsx'
import EcheancierFactures from '../components/EcheancierFactures.jsx'
import Rentabilite from '../components/Rentabilite.jsx'
import SuiviBudgetCarburant from '../components/SuiviBudgetCarburant.jsx'
import Tresorerie from '../components/Tresorerie.jsx'

/**
 * La situation financière de la compagnie, telle que la lisent le PDG et son secrétaire général : trésorerie en temps réel,
 * budget carburant, rentabilité par ligne et par gare (export Excel et PDF), échéancier des paiements. La saisie appartient
 * au directeur financier.
 */
export default function FinancesPage() {
  return (
    <Layout title="Finances">
      <h2 className="section-title">Trésorerie</h2>
      <Tresorerie />

      <h2 className="section-title">Budget carburant</h2>
      <SuiviBudgetCarburant />

      <h2 className="section-title">Rentabilité</h2>
      <Rentabilite />

      <h2 className="section-title">Paiements à venir</h2>
      <EcheancierFactures />
    </Layout>
  )
}
