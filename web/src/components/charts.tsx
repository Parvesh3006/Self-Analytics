"use client";

import { LineChart, MapChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { SVGRenderer } from "echarts/renderers";
import { useEffect, useRef, useState } from "react";
import { feature } from "topojson-client";
import { ISO_NUMERIC } from "@/lib/iso-numeric";

echarts.use([MapChart, LineChart, GridComponent, TooltipComponent, LegendComponent, VisualMapComponent, SVGRenderer]);

const INK = "#43526f";
const GRID = "#e1e0d9";
export const SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];
const TOOLTIP = { backgroundColor: "#0f1f3d", borderWidth: 0, textStyle: { color: "#fff", fontSize: 12, fontFamily: "inherit" }, extraCssText: "border-radius:4px;" };

function useChart(option: any, onClick?: (params: any) => void, ready = true) {
  const ref = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const click = useRef(onClick);
  click.current = onClick;
  useEffect(() => {
    if (!ref.current) return;
    const instance = echarts.init(ref.current, undefined, { renderer: "svg" });
    chart.current = instance;
    instance.on("click", (p) => click.current?.(p));
    const observer = new ResizeObserver(() => instance.resize());
    observer.observe(ref.current);
    return () => { observer.disconnect(); instance.dispose(); chart.current = null; };
  }, []);
  useEffect(() => { if (ready) chart.current?.setOption(option, true); }, [option, ready]);
  return ref;
}

/** A ring spanning the date line would be drawn as a band across the whole map, so its far side is pinned to the edge. */
function closeAntimeridian(ring: number[][]) {
  const lons = ring.map((p) => p[0]);
  if (Math.max(...lons) - Math.min(...lons) <= 180) return;
  for (const point of ring) if (point[0] < 0) point[0] = 180;
}

let worldReady: Promise<void> | null = null;
function loadWorld() {
  worldReady ??= fetch("/world-50m.json").then((r) => r.json()).then((topology) => {
    const geo: any = feature(topology, topology.objects.countries);
    for (const f of geo.features) {
      f.properties.code = ISO_NUMERIC[String(f.id).padStart(3, "0")] ?? "";
      const polygons = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
      for (const rings of polygons) for (const ring of rings) closeAntimeridian(ring);
    }
    echarts.registerMap("world", { ...geo, features: geo.features.filter((f: any) => f.properties.name !== "Antarctica").map((f: any) => ({ ...f, properties: { ...f.properties, name: f.properties.code || f.properties.name } })) });
  });
  return worldReady;
}

export function WorldMap({ rows, selected, onPick }: { rows: { code: string; name: string; jobs: number }[]; selected: string[]; onPick: (code: string) => void }) {
  const [ready, setReady] = useState(false);
  useEffect(() => { loadWorld().then(() => setReady(true)); }, []);
  const names = Object.fromEntries(rows.map((r) => [r.code, r.name]));
  const max = Math.max(...rows.map((r) => r.jobs), 1);
  const option = {
    tooltip: { ...TOOLTIP, trigger: "item", formatter: (p: any) => names[p.name] ? `<b>${names[p.name]}</b><br/>${Number(p.value).toLocaleString("en")} open jobs` : "No jobs collected" },
    visualMap: {
      type: "continuous", min: 1, max: Math.max(max, 10), left: 4, bottom: 4, calculable: false, itemWidth: 10, itemHeight: 90, text: [`${max.toLocaleString("en")} jobs`, "Few"],
      textStyle: { color: INK, fontSize: 11 }, inRange: { color: ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"] }, outOfRange: { color: "#e6ebf3" },
    },
    series: [{
      type: "map", map: "world", roam: false, top: 2, bottom: 2, left: 2, right: 2, selectedMode: false, nameProperty: "name",
      itemStyle: { areaColor: "#e6ebf3", borderColor: "#fcfcfb", borderWidth: 0.6 },
      emphasis: { label: { show: false }, itemStyle: { areaColor: "#c8202f" } },
      data: rows.map((r) => ({ name: r.code, value: r.jobs, itemStyle: selected.includes(r.code) ? { borderColor: "#c8202f", borderWidth: 1.5 } : undefined })),
    }],
  };
  const ref = useChart(option, (p) => { if (names[p.name]) onPick(p.name); }, ready);
  return <div ref={ref} className="h-[23rem] w-full" role="img" aria-label="World map of open jobs by country. The same numbers are in the table below." />;
}

export function TrendLines({ weeks, series, unit = "%" }: { weeks: string[]; series: { name: string; values: number[]; color: string }[]; unit?: string }) {
  const labels = weeks.map((w) => new Date(w).toLocaleDateString("en-GB", { day: "2-digit", month: "short" }));
  const option = {
    grid: { left: 42, right: 18, top: 16, bottom: 26 },
    tooltip: { ...TOOLTIP, trigger: "axis", axisPointer: { type: "line", lineStyle: { color: "#b9c4d8" } }, valueFormatter: (v: number) => `${v}${unit}` },
    xAxis: { type: "category", data: labels, boundaryGap: false, axisLine: { lineStyle: { color: "#c3c2b7" } }, axisTick: { show: false }, axisLabel: { color: INK, fontSize: 11, hideOverlap: true } },
    yAxis: { type: "value", min: 0, splitLine: { lineStyle: { color: GRID } }, axisLabel: { color: INK, fontSize: 11, formatter: `{value}${unit}` } },
    series: series.map((s) => ({
      name: s.name, type: "line", data: s.values, showSymbol: s.values.length < 3, symbolSize: 8, lineStyle: { width: 2, color: s.color }, itemStyle: { color: s.color }, emphasis: { focus: "series" },
    })),
  };
  const ref = useChart(option);
  return <div ref={ref} className="h-72 w-full" role="img" aria-label="Line chart of weekly skill demand. A table view is available." />;
}
