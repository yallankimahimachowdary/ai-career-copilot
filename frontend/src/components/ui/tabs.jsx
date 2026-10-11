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

  const renderChildren = (elements) => {
    return React.Children.map(elements, (child) => {
      if (!React.isValidElement(child)) return child
      if (child.type === React.Fragment) {
        return renderChildren(child.props.children)
      }
      return React.cloneElement(child, {
        activeTab,
        onTabChange: handleTabChange,
      })
    })
  }

  return (
    <div className={cn("w-full space-y-4", className)}>
      {renderChildren(children)}
    </div>
  )
}

export function TabsList({ children, className, activeTab, onTabChange }) {
  return (
    <div
      className={cn(
        "inline-flex h-11 items-center justify-start rounded-xl bg-[#EDE7F6] p-1 border border-[#DDD6E7] text-[#5C5C7A] gap-1",
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
          ? "bg-white text-[#7A2D4A] shadow-xs font-semibold border border-[#DDD6E7]"
          : "text-[#5C5C7A] hover:text-[#3A3A52] hover:bg-white/60",
        className
      )}
    >
      {children}
    </button>
  )
}

export function TabsContent({ value, activeTab, children, className }) {
  if (value !== activeTab) return null
  return (
    <div
      tabIndex={0}
      className={cn("mt-2 ring-offset-[#FAF7F3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#7A2D4A]", className)}
    >
      {children}
    </div>
  )
}
