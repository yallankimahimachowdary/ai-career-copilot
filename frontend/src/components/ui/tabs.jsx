import * as React from "react"
import { cn } from "@/lib/utils"

export function Tabs({ defaultValue, value, onValueChange, children, className }) {
  const [activeTab, setActiveTab] = React.useState(value || defaultValue)

  React.useEffect(() => {
    if (value !== undefined) {
      setActiveTab(value)
    }
  }, [value])

  const handleTabChange = (tab) => {
    setActiveTab(tab)
    if (onValueChange) {
      onValueChange(tab)
    }
  }

  return (
    <div className={cn("w-full space-y-4", className)}>
      {React.Children.map(children, (child) => {
        if (!React.isValidElement(child)) return null
        return React.cloneElement(child, {
          activeTab,
          onTabChange: handleTabChange,
        })
      })}
    </div>
  )
}

export function TabsList({ children, className, activeTab, onTabChange }) {
  return (
    <div
      className={cn(
        "inline-flex h-11 items-center justify-start rounded-xl bg-slate-900/90 p-1 border border-slate-800 text-slate-400 gap-1",
        className
      )}
    >
      {React.Children.map(children, (child) => {
        if (!React.isValidElement(child)) return null
        return React.cloneElement(child, {
          isActive: activeTab === child.props.value,
          onClick: () => onTabChange(child.props.value),
        })
      })}
    </div>
  )
}

export function TabsTrigger({ value, children, className, isActive, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center justify-center whitespace-nowrap rounded-lg px-3.5 py-1.5 text-sm font-medium transition-all duration-150 cursor-pointer",
        isActive
          ? "bg-slate-800 text-white shadow-sm font-semibold text-blue-400"
          : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/40",
        className
      )}
    >
      {children}
    </button>
  )
}

export function TabsContent({ value, children, className, activeTab }) {
  if (activeTab !== value) return null
  return <div className={cn("animate-in fade-in-50 duration-200", className)}>{children}</div>
}
