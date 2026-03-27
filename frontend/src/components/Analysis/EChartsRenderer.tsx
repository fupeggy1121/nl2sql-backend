import ReactECharts from 'echarts-for-react'
import type { ChartData } from '../../types/analytics'

interface Props {
  chart: ChartData
  height?: number
}

export function EChartsRenderer({ chart, height = 320 }: Props) {
  // Strip our internal _renderer key before passing to echarts
  const { _renderer: _r, ...option } = chart
  return (
    <ReactECharts
      option={option}
      style={{ height, width: '100%' }}
      opts={{ renderer: 'canvas' }}
    />
  )
}
