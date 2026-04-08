export async function getAuthToken(_baseURL: string): Promise<string> {
  const resp = await fetch('http://localhost:8000/api/auth/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      secret: 'eclusa-dev-secret-0123456789012345678901234',
    }),
  })
  const data = await resp.json()
  return data.access_token
}
