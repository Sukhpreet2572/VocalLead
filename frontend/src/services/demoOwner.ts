export function demoOwner(): string {
  const name = 'vocalead-demo-owner'
  let value = localStorage.getItem(name)
  if (!value) {
    value = Array.from(crypto.getRandomValues(new Uint8Array(32)), byte => byte.toString(16).padStart(2, '0')).join('')
    localStorage.setItem(name, value)
  }
  return value
}
