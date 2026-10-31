import React from 'react'
import { signalColor } from '../lib/utils'

interface Props {
  score: number   // 0-100
  signal: string
}

export default function TimingGauge({ score, signal }: Props) {
  // Arc: 180° sweep from left to right
  const angle = -180 + (score / 100) * 180   // -180 (left) → 0 (right)
  const rad = (angle * Math.PI) / 180
  const cx = 56, cy = 56, r = 40
  const nx = cx + r * Math.cos(rad)
  const ny = cy + r * Math.sin(rad)

  const gaugeColor =
    score >= 70 ? '#22c55e' : score >= 50 ? '#f59e0b' : score >= 30 ? '#f97316' : '#ef4444'

  return (
    <div className="flex flex-col items-center">
      <svg width="112" height="64" viewBox="0 0 112 64">
        {/* Background arc */}
        <path
          d="M 16 56 A 40 40 0 0 1 96 56"
          fill="none"
          stroke="#334155"
          strokeWidth="8"
          strokeLinecap="round"
        />
        {/* Filled arc */}
        <path
          d={`M 16 56 A 40 40 0 ${score > 50 ? 1 : 0} 1 ${nx.toFixed(1)} ${ny.toFixed(1)}`}
          fill="none"
          stroke={gaugeColor}
          strokeWidth="8"
          strokeLinecap="round"
        />
        {/* Center score */}
        <text
          x="56"
          y="52"
          textAnchor="middle"
          fontSize="16"
          fontWeight="bold"
          fill={gaugeColor}
        >
          {Math.round(score)}
        </text>
      </svg>
      <p className={`text-xs font-bold mt-1 ${signalColor(signal)}`}>{signal}</p>
    </div>
  )
}

