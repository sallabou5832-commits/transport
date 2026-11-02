import react from '@vitejs/plugin-react'
import { configDefaults, defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    // Les parcours dans le navigateur (e2e/) se lancent par « npm run e2e » ou « npm run e2e:pw », jamais par Vitest.
    exclude: [...configDefaults.exclude, 'e2e/**', 'dist-e2e/**'],
  },
})
