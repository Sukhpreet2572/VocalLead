/** Run the actual frontend API client against a live backend without a browser.
 * Usage: node --experimental-vm-modules scripts/smoke-api-client.mjs
 * This verifies HTTP/client behaviour, not browser rendering or browser CORS enforcement.
 */
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { SourceTextModule } from 'node:vm'

const requireFrontend = createRequire(new URL('../frontend/package.json', import.meta.url))
const ts = requireFrontend('typescript')
const source = await readFile(new URL('../frontend/src/services/api.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
})
globalThis.window = { setTimeout }
const client = new SourceTextModule(outputText, {
  initializeImportMeta(meta) {
    meta.env = { VITE_API_BASE_URL: process.env.SMOKE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1' }
  },
})
await client.link(() => { throw new Error('Unexpected runtime import in API client') })
await client.evaluate()
const snapshot = await client.namespace.getServiceSnapshot(new AbortController().signal)
assert.equal(snapshot.health.data?.status, 'healthy', snapshot.health.error)
assert.equal(snapshot.ready.data?.database, 'connected', snapshot.ready.error)
assert.equal(snapshot.system.data?.backend, 'available', snapshot.system.error)
assert.equal(Object.keys(snapshot.system.data.integrations).length, 6)
for (const integration of Object.values(snapshot.system.data.integrations)) {
  assert.equal(integration.connectivity, 'not_verified')
}
console.log('PASS: actual frontend API client received live health, readiness and development status.')
