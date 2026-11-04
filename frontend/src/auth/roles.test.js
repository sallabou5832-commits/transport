import { describe, expect, it } from 'vitest'
import { POLES } from '../lib/rh.js'
import { ALL_ROLES, POLE_DU_ROLE } from './roles.js'

describe('POLE_DU_ROLE', () => {
  it('range chaque poste dans un pôle (l’opérateur de la plateforme à part)', () => {
    expect(Object.keys(POLE_DU_ROLE).sort()).toEqual([...ALL_ROLES].sort())
    for (const role of ALL_ROLES) {
      expect([...Object.keys(POLES), 'plateforme']).toContain(POLE_DU_ROLE[role])
    }
    expect(POLE_DU_ROLE.superadmin).toBe('plateforme')
  })
})
