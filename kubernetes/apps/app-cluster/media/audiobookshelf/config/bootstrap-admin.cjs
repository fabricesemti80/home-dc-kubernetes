const { readFileSync } = require('node:fs')
const { setTimeout: delay } = require('node:timers/promises')

const baseUrl = 'http://127.0.0.1:13378'

function credential(key) {
  const value = readFileSync(`/run/admin-credentials/${key}`, 'utf8')
  if (!value.trim()) throw new Error('Missing admin credential')
  return value
}

async function getStatus() {
  try {
    const response = await fetch(`${baseUrl}/status`, { signal: AbortSignal.timeout(4000) })
    return response.ok ? await response.json() : null
  } catch {
    return null
  }
}

async function bootstrap() {
  for (let attempt = 0; attempt < 90; attempt++) {
    const status = await getStatus()
    if (status?.isInit === true) return
    if (status?.isInit === false) {
      const username = credential('AUDIOBOOKSHELF_ADMIN_USERNAME')
      const password = credential('AUDIOBOOKSHELF_ADMIN_PASSWORD')
      const response = await fetch(`${baseUrl}/init`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ newRoot: { username, password } }),
        signal: AbortSignal.timeout(10000),
      })
      if (!response.ok || (await getStatus())?.isInit !== true) {
        throw new Error('Admin setup rejected')
      }
      return
    }
    await delay(2000)
  }
  throw new Error('Server unavailable')
}

bootstrap().catch(() => {
  // Never write credentials, request payloads or response bodies to pod events.
  console.error('Audiobookshelf admin bootstrap failed; check Doppler keys and server availability.')
  process.exitCode = 1
})
