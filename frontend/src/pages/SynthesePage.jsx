import Layout from '../components/Layout.jsx'
import ReportingJuridique from '../components/ReportingJuridique.jsx'
import SyntheseRh from '../components/SyntheseRh.jsx'

/** Ce que la Direction Générale lit des fonctions supports : la situation juridique (reporting) et les chiffres de la gestion RH. */
export default function SynthesePage() {
  return (
    <Layout title="Synthèse RH et juridique">
      <h2 className="section-title">Situation juridique</h2>
      <ReportingJuridique />

      <h2 className="section-title">Ressources humaines</h2>
      <SyntheseRh />
    </Layout>
  )
}
