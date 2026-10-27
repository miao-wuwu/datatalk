import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import type { ChartSpec } from "../types";

const PALETTE = ["#4f46e5", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#14b8a6", "#f97316"];

function option(spec: ChartSpec): echarts.EChartsOption {
  const data = spec.data ?? [];
  const base: echarts.EChartsOption = {
    color: PALETTE,
    tooltip: { trigger: spec.type === "pie" ? "item" : "axis" },
    grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
  };

  if (spec.type === "pie") {
    return {
      ...base,
      series: [
        {
          type: "pie",
          radius: ["38%", "68%"],
          itemStyle: { borderRadius: 6, borderColor: "#fff", borderWidth: 2 },
          label: { formatter: "{b}\n{d}%", fontSize: 11 },
          data,
        },
      ],
    };
  }

  return {
    ...base,
    xAxis: {
      type: "category",
      data: data.map((d) => d.name),
      axisLabel: { fontSize: 11, interval: 0, rotate: data.length > 8 ? 30 : 0, color: "#64748b" },
      axisLine: { lineStyle: { color: "#e2e8f0" } },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { color: "#f1f5f9" } },
      axisLabel: { fontSize: 11, color: "#94a3b8" },
    },
    series: [
      {
        type: spec.type === "line" ? "line" : "bar",
        data: data.map((d) => d.value),
        smooth: true,
        barMaxWidth: 42,
        itemStyle: { borderRadius: [4, 4, 0, 0] },
        areaStyle: spec.type === "line" ? { opacity: 0.12 } : undefined,
      },
    ],
  };
}

export function ChartView({ spec, height = 320 }: { spec: ChartSpec; height?: number }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const chart = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    chart.current = echarts.init(ref.current);
    const onResize = () => chart.current?.resize();
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.current?.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    chart.current?.setOption(option(spec), true);
  }, [spec]);

  return <div ref={ref} className="chart" style={{ height }} />;
}