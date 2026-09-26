import { useState } from 'react'
import Layout from '../components/Layout.jsx'
import BudgetsCarburant from '../components/BudgetsCarburant.jsx'
import DepensesFinance from '../components/DepensesFinance.jsx'
import FacturesFournisseurs from '../components/FacturesFournisseurs.jsx'
import Rentabilite from '../components/Rentabilite.jsx'
import SoldeInitial from '../components/SoldeInitial.jsx'
import SuiviBudgetCarburant from '../components/SuiviBudgetCarburant.jsx'
import Tresorerie from '../components/Tresorerie.jsx'

/**
 * La comptabilité de la compagnie, tenue par le directeur financier : trésorerie, budget carburant par ligne, rentabilité, dépenses,
 * fournisseurs et échéancier des paiements. Le PDG et son secrétaire général en lisent la synthèse (page « Finances »).
 */
export default function ComptabilitePage() {
  // Une dépense, un budget, un paiement ou un solde changent la trésorerie, le suivi du budget et la rentabilité : chaque saisie
  // incrémente `version`, ce qui les recharge sans recharger toute la page.
  const [version, setVersion] = useState(0)
  const enregistre = () => setVersion((v) => v + 1)

  return (
    <Layout title="Comptabilité">
      <h2 className="section-title">Trésorerie</h2>
      <Tresorerie version={version} />
      <SoldeInitial onChange={enregistre} />

      <h2 className="section-title">Budget carburant</h2>
      <SuiviBudgetCarburant version={version} />
      <BudgetsCarburant onChange={enregistre} />

      <h2 className="section-title">Rentabilité</h2>
      <Rentabilite version={version} />

      <h2 className="section-title">Dépenses</h2>
      <DepensesFinance onChange={enregistre} version={version} />

      <h2 className="section-title">Fournisseurs et paiements</h2>
      <FacturesFournisseurs onChange={enregistre} />
    </Layout>
  )
}
