import React, { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { useAuth } from "@/context/AuthContext"
import { Bot, Eye, EyeOff, Loader2, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()

  const [fullName, setFullName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!email.trim() || !password) {
      setError("Email and password are required.")
      return
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters.")
      return
    }

    setIsSubmitting(true)
    setError(null)
    try {
      await register({
        email: email.trim(),
        password,
        full_name: fullName.trim() || undefined,
      })
      navigate("/dashboard", { replace: true })
    } catch (err) {
      setError(err.message || "Registration failed. An account with this email may already exist.")
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
          <p className="text-xs text-[#5C5C7A]">Create your student account to analyze resumes and match roles</p>
        </div>

        {/* Register Card */}
        <div className="rounded-2xl border border-[#DDD6E7] bg-white p-6 sm:p-8 shadow-xs space-y-6">
          <div className="space-y-1">
            <h2 className="text-lg font-semibold text-[#3A3A52]">Student Registration</h2>
            <p className="text-xs text-[#5C5C7A]">Enter your details to create your personalized workspace</p>
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
              <label htmlFor="reg-name" className="block text-xs font-semibold text-[#3A3A52]">
                Full Name
              </label>
              <Input
                id="reg-name"
                type="text"
                name="name"
                autoComplete="name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="e.g. Alex Rivera"
                className="min-h-[46px] border-[#DDD6E7] focus-visible:ring-[#7A2D4A]"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="reg-email" className="block text-xs font-semibold text-[#3A3A52]">
                Email Address
              </label>
              <Input
                id="reg-email"
                type="email"
                name="email"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="alex.rivera@university.edu"
                className="min-h-[46px] border-[#DDD6E7] focus-visible:ring-[#7A2D4A]"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="reg-password" className="block text-xs font-semibold text-[#3A3A52]">
                Password
              </label>
              <div className="relative">
                <Input
                  id="reg-password"
                  type={showPassword ? "text" : "password"}
                  name="password"
                  autoComplete="new-password"
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 8 characters"
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
              <p className="text-[11px] text-[#797996]">Must be at least 8 characters.</p>
            </div>

            <Button
              type="submit"
              disabled={isSubmitting}
              className="w-full min-h-[46px] bg-[#7A2D4A] hover:bg-[#63233B] text-white font-medium text-sm rounded-xl shadow-xs transition-colors"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Creating Account...
                </>
              ) : (
                "Create Student Account"
              )}
            </Button>
          </form>

          <div className="text-center text-xs text-[#5C5C7A]">
            Already have an account?{" "}
            <Link to="/login" className="font-semibold text-[#7A2D4A] hover:underline">
              Sign in
            </Link>
          </div>
        </div>

        <p className="text-center text-[11px] text-[#797996]">
          AI Career Copilot • Multi-Agent Explainable Career Guidance
        </p>
      </div>
    </div>
  )
}

export default RegisterPage
