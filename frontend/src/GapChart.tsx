// Asset data-quality gaps as a bar chart. One series, one hue, no legend; the numbers come from the
// summary endpoint (counted in SQL over the whole inventory) and nothing is computed here.
import ReactECharts from "echarts-for-react";
import type { AssetSummary } from "./api";
import { tokens } from "./theme";

const GAPS: { key: keyof AssetSummary; label: string }[] = [
  { key: "without_owner", label: "Without owner" },
  { key: "without_criticality", label: "Without criticality" },
  { key: "potentially_inactive", label: "Potentially inactive" },
];

export function GapChart({ summary }: { summary: AssetSummary }) {
  const option = {
    backgroundColor: "transparent",
    grid: { left: 8, right: 24, top: 8, bottom: 8, containLabel: true },
    tooltip: {
      trigger: "item",
      backgroundColor: tokens.panel, borderColor: tokens.line, textStyle: { color: tokens.text, fontSize: 12 },
      formatter: (p: { name: string; value: number }) => `${p.name}: <b>${p.value}</b> of ${summary.total_assets} assets`,
    },
    xAxis: {
      type: "value", minInterval: 1,
      axisLine: { show: false }, axisTick: { show: false },
      splitLine: { lineStyle: { color: tokens.line } },
      axisLabel: { color: tokens.muted, fontSize: 11 },
    },
    yAxis: {
      type: "category", inverse: true, data: GAPS.map((g) => g.label),
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: tokens.text, fontSize: 12 },
    },
    series: [{
      type: "bar", barWidth: 14,
      data: GAPS.map((g) => summary[g.key] as number),
      itemStyle: { color: tokens.accent, borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: "right", color: tokens.text, fontSize: 12 },
      emphasis: { itemStyle: { borderColor: tokens.bg, borderWidth: 2 } },
    }],
  };
  return <ReactECharts option={option} style={{ height: 150 }} notMerge aria-label="Asset data-quality gaps" />;
}
