import * as React from "react"
import { cn } from "@/lib/utils"

export const Card = React.forwardRef(({ className, children, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "rounded-xl border border-[#DDD6E7] bg-white text-[#3A3A52] shadow-sm transition-all duration-200",
      className
    )}
    {...props}
  >
    {children}
  </div>
))
Card.displayName = "Card"

export const CardHeader = React.forwardRef(({ className, children, ...props }, ref) => (
  <div ref={ref} className={cn("flex flex-col space-y-1.5 p-5 border-b border-[#E5E3EB]", className)} {...props}>
    {children}
  </div>
))
CardHeader.displayName = "CardHeader"

export const CardTitle = React.forwardRef(({ className, children, ...props }, ref) => (
  <h3 ref={ref} className={cn("font-semibold leading-none tracking-tight text-[#3A3A52] text-lg", className)} {...props}>
    {children}
  </h3>
))
CardTitle.displayName = "CardTitle"

export const CardDescription = React.forwardRef(({ className, children, ...props }, ref) => (
  <p ref={ref} className={cn("text-sm text-[#5C5C7A] mt-1", className)} {...props}>
    {children}
  </p>
))
CardDescription.displayName = "CardDescription"

export const CardContent = React.forwardRef(({ className, children, ...props }, ref) => (
  <div ref={ref} className={cn("p-5 pt-4", className)} {...props}>
    {children}
  </div>
))
CardContent.displayName = "CardContent"

export const CardFooter = React.forwardRef(({ className, children, ...props }, ref) => (
  <div ref={ref} className={cn("flex items-center p-5 pt-0 border-t border-[#E5E3EB] mt-4", className)} {...props}>
    {children}
  </div>
))
CardFooter.displayName = "CardFooter"
