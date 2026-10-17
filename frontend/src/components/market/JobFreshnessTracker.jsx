import React, { useState, useEffect } from "react"
import {
  Clock,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Loader2,
  ShieldCheck,
  Database,
  Calendar,
} from "lucide-react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { jobApi } from "@/api/jobApi"

export function JobFreshnessTracker() {
  const [statusData, setStatusData] = useState(null)
  const [isLoadingStatus, setIsLoadingStatus] = useState(true)
  const [isTriggering, setIsTriggering] = useState(false)
  const [actionMessage, setActionMessage] = useState(null)
  const [actionError, setActionError] = useState(null)

  const loadStatus = async () => {
    setIsLoadingStatus(true)
    try {
      const data = await jobApi.getRefreshStatus()
      setStatusData(data)
    } catch (err) {
      console.warn("Could not load job freshness status:", err.message)
    } finally {
      setIsLoadingStatus(false)
    }
  }

  useEffect(() => {
    loadStatus()
  }, [])

  const handleTriggerRefresh = async () => {
    setIsTriggering(true)
    setActionMessage(null)
    setActionError(null)
    try {
      const response = await jobApi.triggerRefresh({
        evaluate_freshness: true,
      })
      setActionMessage(
        `Job refresh initiated successfully (Run ID: ${response.run_id?.slice(0, 8)}...). Status: ${response.status}.`
      )
      // Reload status
      await loadStatus()
    } catch (err) {
      setActionError(`Job refresh failed: ${err.message}`)
    } finally {
      setIsTriggering(false)
    }
  }

  const lastRun = statusData?.last_run
  const freshnessSummary = lastRun?.freshness_summary || {}
  const isRunning = Boolean(statusData?.is_running || isTriggering)

  return (
    <Card className="border-[#DDD6E7] bg-white shadow-xs">
      <CardHeader className="pb-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <CardTitle className="text-base flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-[#7A2D4A]" />
            Job Market Data Freshness & Ingestion Health
          </CardTitle>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={loadStatus}
              disabled={isLoadingStatus || isRunning}
              className="text-xs h-8 border-[#DDD6E7] text-[#5C5C7A] hover:text-[#3A3A52]"
            >
              <RefreshCw className={`h-3 w-3 mr-1.5 ${isLoadingStatus ? "animate-spin" : ""}`} />
              Check Status
            </Button>
            <Button
              size="sm"
              onClick={handleTriggerRefresh}
              disabled={isRunning}
              className="text-xs h-8 bg-[#7A2D4A] hover:bg-[#63233B] text-white"
            >
              {isRunning ? (
                <>
                  <Loader2 className="h-3 w-3 animate-spin mr-1.5" />
                  Refreshing...
                </>
              ) : (
                <>
                  <Database className="h-3 w-3 mr-1.5" />
                  Trigger Ingestion Refresh
                </>
              )}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {actionMessage && (
          <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
            <span>{actionMessage}</span>
          </div>
        )}

        {actionError && (
          <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-xs text-red-800 flex items-center gap-2">
            <XCircle className="h-4 w-4 text-red-600 shrink-0" />
            <span>{actionError}</span>
          </div>
        )}

        {/* Live Status Summary Badges */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 space-y-1">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-emerald-800">
              Fresh Postings
            </span>
            <div className="text-lg font-bold text-emerald-900 font-mono">
              {freshnessSummary.fresh_count !== undefined
                ? freshnessSummary.fresh_count.toLocaleString()
                : "Active"}
            </div>
            <p className="text-[10px] text-emerald-700">Verified active & recently seen</p>
          </div>

          <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 space-y-1">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-amber-800">
              Stale Postings
            </span>
            <div className="text-lg font-bold text-amber-900 font-mono">
              {freshnessSummary.stale_count !== undefined
                ? freshnessSummary.stale_count.toLocaleString()
                : "0"}
            </div>
            <p className="text-[10px] text-amber-700">&gt; 30 days without refresh</p>
          </div>

          <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 space-y-1">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-rose-800">
              Expired Postings
            </span>
            <div className="text-lg font-bold text-rose-900 font-mono">
              {freshnessSummary.expired_count !== undefined
                ? freshnessSummary.expired_count.toLocaleString()
                : "0"}
            </div>
            <p className="text-[10px] text-rose-700">Excluded from recommendations</p>
          </div>

          <div className="p-3 rounded-xl bg-[#FAF7F3] border border-[#DDD6E7] space-y-1">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[#5C5C7A]">
              Ingestion State
            </span>
            <div className="text-lg font-bold text-[#3A3A52] font-mono">
              {statusData?.is_running ? "Running" : "Idle"}
            </div>
            <p className="text-[10px] text-[#5C5C7A]">Scheduler ready</p>
          </div>
        </div>

        {/* Detailed Run Information */}
        {lastRun && (
          <div className="rounded-xl border border-[#E5E3EB] bg-[#FAF7F3] p-3.5 space-y-2 text-xs">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Clock className="h-3.5 w-3.5 text-[#7A2D4A]" />
                <span className="font-semibold text-[#3A3A52]">Last Completed Ingestion Cycle:</span>
                <span className="font-mono text-[#5C5C7A]">
                  {lastRun.finished_at
                    ? new Date(lastRun.finished_at).toLocaleString()
                    : "Recently"}
                </span>
              </div>
              <Badge
                variant="outline"
                className={
                  lastRun.status === "completed"
                    ? "bg-emerald-50 text-emerald-800 border-emerald-300"
                    : lastRun.status === "failed"
                    ? "bg-red-50 text-red-800 border-red-300"
                    : "bg-amber-50 text-amber-800 border-amber-300"
                }
              >
                {lastRun.status?.toUpperCase() || "RECORDED"}
              </Badge>
            </div>

            <div className="flex flex-wrap gap-x-6 gap-y-1 text-[#5C5C7A] text-[11px] pt-1">
              {lastRun.duration_seconds !== null && (
                <span>Duration: {lastRun.duration_seconds?.toFixed(2)}s</span>
              )}
              {lastRun.sources && Array.isArray(lastRun.sources) && (
                <span>Sources: {lastRun.sources.join(", ")}</span>
              )}
              {lastRun.run_id && <span>Run ID: {lastRun.run_id.slice(0, 8)}...</span>}
            </div>

            {lastRun.error_message && (
              <div className="p-2 rounded bg-red-100 text-red-800 text-[11px] border border-red-200">
                <strong>Ingestion Error ({lastRun.error_category}):</strong> {lastRun.error_message}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default JobFreshnessTracker
