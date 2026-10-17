import React, { useState } from "react"
import { Link, useNavigate, useLocation } from "react-router-dom"
import { useAuth } from "@/context/AuthContext"
import { Bot, Eye, EyeOff, Loader2, Sparkles, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = location.state?.from?.pathname || "/dashboard"

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!email.trim() || !password) {
      setError("Please enter both email and password.")
      return
    }

    setIsSubmitting(true)
    setError(null)
    try {
      await login({ email: email.trim(), password })
      navigate(from, { replace: true })
    } catch (err) {
      setError(err.message || "Invalid email or password.")
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleDemoLogin = async () => {
    setEmail("student@career.local")
    setPassword("StudentPass123!")
    setIsSubmitting(true)
    setError(null)
    try {
      await login({ email: "student@career.local", password: "StudentPass123!" })
      navigate(from, { replace: true })
    } catch {
      // If demo user not in DB yet, prompt registering or standard fallback
      setError("Demo credentials not registered on backend yet. Please register an account below.")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#FAF7F3] p-4 sm:p-6 lg:p-8 font-sans">
      <div className="w-full max-w-md space-y-6">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-[#7A2D4A] shadow-sm mb-1">
            <Bot className="h-6 w-6 text-white" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-[#3A3A52]">AI Career Copilot</h1>
          <p className="text-xs text-[#5C5C7A]">Sign in to access your student career intelligence workspace</p>
        </div>

        {/* Login Card */}
        <div className="rounded-2xl border border-[#DDD6E7] bg-white p-6 sm:p-8 shadow-xs space-y-6">
          <div className="space-y-1">
            <h2 className="text-lg font-semibold text-[#3A3A52]">Student Login</h2>
            <p className="text-xs text-[#5C5C7A]">Enter your credentials to continue your career journey</p>
          </div>

          {error && (
            <div
              role="alert"
              className="flex items-start gap-2.5 rounded-xl bg-red-50 p-3.5 text-xs text-red-800 border border-red-200"
            >
              <AlertCircle className="h-4 w-4 shrink-0 text-red-600 mt-0.5" />
              <div className="flex-1 font-medium">{error}</div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <div className="space-y-1.5">
              <label htmlFor="login-email" className="block text-xs font-semibold text-[#3A3A52]">
                Email Address
              </label>
              <Input
                id="login-email"
                type="email"
                name="email"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@university.edu"
                className="min-h-[46px] border-[#DDD6E7] focus-visible:ring-[#7A2D4A]"
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label htmlFor="login-password" className="block text-xs font-semibold text-[#3A3A52]">
                  Password
                </label>
              </div>
              <div className="relative">
                <Input
                  id="login-password"
                  type={showPassword ? "text" : "password"}
                  name="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  className="min-h-[46px] pr-11 border-[#DDD6E7] focus-visible:ring-[#7A2D4A]"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  aria-pressed={showPassword}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#797996] hover:text-[#3A3A52] p-1.5 focus:outline-none"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <Button
              type="submit"
              disabled={isSubmitting}
              className="w-full min-h-[46px] bg-[#7A2D4A] hover:bg-[#63233B] text-white font-medium text-sm rounded-xl shadow-xs transition-colors"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Signing In...
                </>
              ) : (
                "Sign In"
              )}
            </Button>
          </form>

          <div className="relative flex items-center justify-center">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-[#DDD6E7]" />
            </div>
            <span className="relative bg-white px-3 text-[11px] uppercase tracking-wider text-[#797996] font-medium">
              Or explore
            </span>
          </div>

          <Button
            type="button"
            variant="secondary"
            onClick={handleDemoLogin}
            disabled={isSubmitting}
            className="w-full min-h-[42px] border border-[#DDD6E7] bg-[#FAF7F3] hover:bg-[#EDE7F6] text-[#7A2D4A] text-xs font-semibold rounded-xl transition-colors"
          >
            <Sparkles className="h-3.5 w-3.5 mr-1.5 text-[#7A2D4A]" />
            Try Pre-seeded Demo Credentials
          </Button>

          <div className="text-center text-xs text-[#5C5C7A]">
            Don't have an account yet?{" "}
            <Link to="/register" className="font-semibold text-[#7A2D4A] hover:underline">
              Create an account
            </Link>
          </div>
        </div>

        {/* Footer info */}
        <p className="text-center text-[11px] text-[#797996]">
          AI Career Copilot • Multi-Agent Explainable Career Guidance
        </p>
      </div>
    </div>
  )
}

export default LoginPage
