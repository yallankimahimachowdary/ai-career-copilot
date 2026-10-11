import { clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

export function formatCurrency(amount, currency = "INR") {
  if (amount == null || amount === 0 || amount === "0") return "Not disclosed"
  const num = Number(amount)
  if (isNaN(num) || num <= 0) return "Not disclosed"

  if (currency === "INR") {
    if (num >= 100000) {
      const lakhs = num / 100000
      const formatted = lakhs % 1 === 0 ? lakhs.toFixed(0) : lakhs.toFixed(1)
      return `₹${formatted} LPA`
    }
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(num)
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(num)
}

export function formatPercent(value) {
  if (value == null) return "0%"
  return `${Math.round(value * 100)}%`
}

export function formatDate(dateString) {
  if (!dateString) return ""
  try {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    })
  } catch {
    return dateString
  }
}
