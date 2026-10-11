import React from "react"
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  ReferenceLine,
} from "recharts"
import { Info } from "lucide-react"

export function ShapWaterfall({ explanations = [] }) {
  if (!explanations || explanations.length === 0) {
    return (
      <div className="p-6 text-center text-xs text-[#5C5C7A] border border-[#DDD6E7] rounded-xl bg-white">
        No SHAP attribution values generated for this match.
      </div>
    )
  }

  // Format data for Recharts horizontal diverging bar chart
  const data = explanations.map((item) => ({
    name: item.display_name || item.feature_name,
    shap: Number(item.shap_value.toFixed(3)),
    impact: item.impact || `${item.shap_value > 0 ? "+" : ""}${(item.shap_value * 100).toFixed(1)}%`,
    description: item.description,
    isPositive: item.shap_value >= 0,
  }))

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const d = payload[0].payload
      return (
        <div className="p-3 rounded-xl bg-white border border-[#DDD6E7] shadow-lg max-w-xs text-xs space-y-1 z-50">
          <div className="flex items-center justify-between font-bold text-[#3A3A52]">
            <span>{d.name}</span>
            <span className={d.isPositive ? "text-emerald-700" : "text-red-700"}>{d.impact}</span>
          </div>
          <p className="text-[#5C5C7A] leading-relaxed">{d.description}</p>
          <div className="text-[10px] text-[#5C5C7A] font-mono pt-1">SHAP value: {d.shap}</div>
        </div>
      )
    }
    return null
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between text-xs text-[#5C5C7A]">
        <span className="flex items-center gap-1.5 font-medium text-[#3A3A52]">
          <Info className="h-3.5 w-3.5 text-[#7A2D4A]" />
          TreeSHAP Local Feature Attribution
        </span>
        <div className="flex items-center gap-3 text-[11px]">
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-emerald-600" /> Positive Fit Drivers
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-red-600" /> Missing Requirement Penalties
          </span>
        </div>
      </div>

      <div className="h-64 w-full bg-white rounded-xl p-2 border border-[#DDD6E7]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 10, right: 30, left: 100, bottom: 5 }}
          >
            <XAxis
              type="number"
              domain={["auto", "auto"]}
              tick={{ fill: "#5C5C7A", fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: "#DDD6E7" }}
            />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ fill: "#3A3A52", fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: "#DDD6E7" }}
              width={100}
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine x={0} stroke="#DDD6E7" strokeDasharray="3 3" />
            <Bar dataKey="shap" radius={[4, 4, 4, 4]}>
              {data.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.isPositive ? "#059669" : "#DC2626"}
                  fillOpacity={0.85}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Plain English explanation summary list */}
      <div className="space-y-2 pt-1">
        {explanations.map((exp, idx) => (
          <div
            key={idx}
            className="flex items-start gap-2.5 p-2.5 rounded-lg bg-[#FAF7F3] border border-[#DDD6E7] text-xs"
          >
            <span
              className={`font-mono font-bold px-1.5 py-0.5 rounded text-[10px] shrink-0 mt-0.5 ${
                exp.shap_value >= 0
                  ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                  : "bg-red-50 text-red-700 border border-red-200"
              }`}
            >
              {exp.impact || (exp.shap_value >= 0 ? `+${(exp.shap_value * 100).toFixed(1)}%` : `${(exp.shap_value * 100).toFixed(1)}%`)}
            </span>
            <div className="space-y-0.5">
              <span className="font-semibold text-[#3A3A52]">{exp.display_name}: </span>
              <span className="text-[#5C5C7A]">{exp.description}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
