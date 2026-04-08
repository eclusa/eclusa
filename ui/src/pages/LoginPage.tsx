import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useAuth } from '@/auth/useAuth'

export function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const auth = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setIsSubmitting(true)

    try {
      const response = await fetch('/api/auth/token', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      })

      if (!response.ok) {
        const errorBody = (await response.json().catch(() => ({}))) as { detail?: string }
        throw new Error(errorBody.detail ?? 'Invalid credentials')
      }

      const data = (await response.json()) as { access_token?: string }
      if (!data.access_token) {
        throw new Error('Invalid credentials')
      }

      auth.login(data.access_token)
      navigate('/cascades', { replace: true })
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Invalid credentials')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-zinc-950 via-zinc-950 to-zinc-900 px-4 text-zinc-100">
      <Card className="w-full max-w-md border-zinc-800 bg-zinc-900/90 text-zinc-100 shadow-2xl shadow-black/40">
        <CardHeader className="space-y-2 border-b border-zinc-800 p-6">
          <div className="text-xs font-mono uppercase tracking-[0.35em] text-zinc-500">Eclusa</div>
          <CardTitle className="text-2xl font-semibold">Back office login</CardTitle>
          <p className="text-sm leading-relaxed text-zinc-400">Sign in with your email and password.</p>
        </CardHeader>
        <CardContent className="p-6">
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="space-y-2">
              <label htmlFor="email" className="text-xs font-mono uppercase tracking-[0.2em] text-zinc-400">
                Email
              </label>
              <Input
                id="email"
                name="email"
                type="email"
                value={email}
                onChange={(event) => {
                  setEmail(event.target.value)
                  if (error) {
                    setError('')
                  }
                }}
                autoComplete="email"
                placeholder="you@example.com"
                className="border-zinc-800 bg-zinc-950 text-zinc-100 placeholder:text-zinc-500 focus-visible:ring-zinc-500"
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="password" className="text-xs font-mono uppercase tracking-[0.2em] text-zinc-400">
                Password
              </label>
              <Input
                id="password"
                name="password"
                type="password"
                value={password}
                onChange={(event) => {
                  setPassword(event.target.value)
                  if (error) {
                    setError('')
                  }
                }}
                autoComplete="current-password"
                placeholder="Password"
                className="border-zinc-800 bg-zinc-950 text-zinc-100 placeholder:text-zinc-500 focus-visible:ring-zinc-500"
              />
            </div>

            {error ? <p className="text-sm text-red-400">{error}</p> : null}

            <div className="space-y-3">
              <Button type="submit" className="w-full bg-zinc-100 text-zinc-950 hover:bg-zinc-200" disabled={isSubmitting}>
                {isSubmitting ? 'Signing in...' : 'Sign in'}
              </Button>
              <div className="text-center">
                <Link
                  to="/register"
                  className="text-xs font-mono uppercase tracking-[0.2em] text-zinc-500 hover:text-zinc-100"
                >
                  Create account
                </Link>
              </div>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
