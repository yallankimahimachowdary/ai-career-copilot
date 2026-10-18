import React from "react"
import {
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Tooltip,
} from "recharts"

export function InterviewRubricRadar({ rubricBreakdown, rubric }) {
  const targetRubric = rubricBreakdown || rubric || {}
  const entries = Object.entries(targetRubric)
  const hasDimensions = entries.length > 0

  const chartData = entries.map(([dim, val]) => ({
    dimension: dim.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    score: typeof val === "number" ? Number(val.toFixed(1)) : 0,
    fullMark: 10,
  }))

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload
      return (
        <div className="p-2.5 rounded-lg bg-white border border-[#DDD6E7] shadow-md text-xs">
          <div className="font-semibold text-[#3A3A52]">{data.dimension}</div>
          <div className="text-[#7A2D4A] font-mono font-bold">
            Score: {data.score} / {data.fullMark}
          </div>
        </div>
      )
    }
    return null
  }

  return (
    <div
      role="region"
      aria-label="Interview Rubric Evaluation Section"
      className="space-y-4 p-4 rounded-xl bg-[#FAF7F3] border border-[#DDD6E7]"
    >
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold text-[#3A3A52]">
          Rubric Dimension Radar Analysis
        </h4>
        <span className="text-[11px] font-mono text-[#5C5C7A]">Scale: 0.0 - 10.0</span>
      </div>

      {hasDimensions ? (
        <div
          role="img"
          aria-label="Interview Rubric Assessment Radar Chart"
          className="h-64 w-full"
        >
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart cx="50%" cy="50%" outerRadius="75%" data={chartData}>
              <PolarGrid stroke="#DDD6E7" />
              <PolarAngleAxis
                dataKey="dimension"
                tick={{ fill: "#3A3A52", fontSize: 11, fontWeight: 500 }}
              />
              <PolarRadiusAxis
                angle={30}
                domain={[0, 10]}
                tick={{ fill: "#5C5C7A", fontSize: 9 }}
              />
              <Tooltip content={<CustomTooltip />} />
              <Radar
                name="Candidate Score"
                dataKey="score"
                stroke="#7A2D4A"
                fill="#7A2D4A"
                fillOpacity={0.45}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="p-6 text-center text-xs text-[#5C5C7A] italic bg-white rounded-lg border border-[#DDD6E7]">
          No rubric dimensions available to render.
        </div>
      )}

      {/* Textual Score Table Fallback for Screen Readers & Non-Visual Access */}
      <div className="overflow-x-auto pt-2">
        <table
          aria-label="Rubric Dimension Scores Table"
          className="w-full text-xs text-left border-collapse border border-[#DDD6E7] bg-white rounded-lg overflow-hidden"
        >
          <thead>
            <tr className="bg-[#EDE7F6] text-[#3A3A52] border-b border-[#DDD6E7]">
              <th scope="col" className="p-2.5 font-semibold">Evaluation Dimension</th>
              <th scope="col" className="p-2.5 font-semibold text-right">Score</th>
              <th scope="col" className="p-2.5 font-semibold text-right">Max Scale</th>
            </tr>
          </thead>
          <tbody>
            {hasDimensions ? (
              entries.map(([dim, val]) => (
                <tr key={dim} className="border-b border-[#DDD6E7] hover:bg-[#FAF7F3]">
                  <td className="p-2.5 text-[#3A3A52] font-medium capitalize">
                    {dim.replace(/_/g, " ")}
                  </td>
                  <td className="p-2.5 font-mono font-bold text-[#7A2D4A] text-right">
                    {typeof val === "number" ? val.toFixed(1) : val}
                  </td>
                  <td className="p-2.5 font-mono text-[#5C5C7A] text-right">10.0</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={3} className="p-3 text-center text-[#5C5C7A] italic">
                  No rubric dimensions recorded.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default InterviewRubricRadar
