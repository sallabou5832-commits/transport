import Layout from '../components/Layout.jsx'
import MaMediation from '../components/MaMediation.jsx'
import MesConges from '../components/MesConges.jsx'
import MesFormations from '../components/MesFormations.jsx'

/**
 * Mon espace : ce que chaque agent, quel que soit son poste, fait pour lui-même auprès des ressources humaines — demander un congé,
 * vérifier ses formations obligatoires, déposer une doléance.
 */
export default function EspacePage() {
  return (
    <Layout title="Mon espace">
      <MesConges />
      <MesFormations />
      <MaMediation />
    </Layout>
  )
}
