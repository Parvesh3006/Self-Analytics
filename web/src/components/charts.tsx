"use client";

import { LineChart, MapChart, ScatterChart } from "echarts/charts";
import { GeoComponent, GridComponent, LegendComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { SVGRenderer } from "echarts/renderers";
import { Minus, Plus, RotateCcw } from "lucide-react";
import { type RefObject, useEffect, useRef, useState } from "react";
import { feature } from "topojson-client";
import { useApi } from "@/lib/api";
import { ISO_NUMERIC } from "@/lib/iso-numeric";

echarts.use([MapChart, LineChart, ScatterChart, GeoComponent, GridComponent, TooltipComponent, LegendComponent, VisualMapComponent, SVGRenderer]);

const INK = "#43526f";
const GRID = "#e1e0d9";
export const SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];
const TOOLTIP = { backgroundColor: "#0f1f3d", borderWidth: 0, textStyle: { color: "#fff", fontSize: 12, fontFamily: "inherit" }, extraCssText: "border-radius:4px;" };

function useChart(option: any, onClick?: (params: any) => void, ready = true, handle?: RefObject<echarts.ECharts | null>) {
  const ref = useRef<HTMLDivElement>(null);
  const local = useRef<echarts.ECharts | null>(null);
  const chart = handle ?? local;
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

export type MapPlace = { name: string; state: string | null; code: string; lat: number; lng: number; jobs: number };
type MapLevel = "country" | "state" | "city";

const MAX_ZOOM = 40;
const levelFor = (zoom: number): MapLevel => (zoom >= 5 ? "city" : zoom >= 2 ? "state" : "country");
const escapeHtml = (text: string) => text.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
const openJobs = (n: number) => `${n.toLocaleString("en")} open job${n === 1 ? "" : "s"}`;
const LEVEL_NOTE: Record<MapLevel, string> = { country: "Zoom in to see states and cities", state: "Showing states. Zoom in for cities", city: "Showing cities" };

export function WorldMap({ rows, selected, onPick, query, onPlace }: { rows: { code: string; name: string; jobs: number }[]; selected: string[]; onPick: (code: string) => void; query: string; onPlace: (place: MapPlace, level: "state" | "city") => void }) {
  const [ready, setReady] = useState(false);
  useEffect(() => { loadWorld().then(() => setReady(true)); }, []);
  const chart = useRef<echarts.ECharts | null>(null);
  const view = useRef<{ zoom: number; center?: number[] }>({ zoom: 1 });
  const [level, setLevel] = useState<MapLevel>("country");
  const [, redraw] = useState(0);
  const places = useApi<MapPlace[]>(level === "country" ? null : `/api/market/map-points?level=${level}${query ? `&${query}` : ""}`);
  const points = level === "country" ? [] : places.data ?? [];

  const names = Object.fromEntries(rows.map((r) => [r.code, r.name]));
  const jobs = Object.fromEntries(rows.map((r) => [r.code, r.jobs]));
  const max = Math.max(...rows.map((r) => r.jobs), 1);
  const maxPlace = Math.max(...points.map((p) => p.jobs), 1);
  const option = {
    tooltip: {
      ...TOOLTIP, trigger: "item",
      formatter: (p: any) => {
        if (p.seriesType === "scatter") {
          const place: MapPlace = p.data.place;
          const area = [level === "city" ? place.state : null, names[place.code]].filter(Boolean).join(", ");
          return `<b>${escapeHtml(place.name)}</b><br/>${area ? `${escapeHtml(area)}<br/>` : ""}${openJobs(place.jobs)}`;
        }
        return names[p.name] ? `<b>${escapeHtml(names[p.name])}</b><br/>${openJobs(jobs[p.name])}` : "No jobs collected";
      },
    },
    visualMap: {
      type: "continuous", seriesIndex: 0, min: 1, max: Math.max(max, 10), left: 4, bottom: 4, calculable: false, itemWidth: 10, itemHeight: 90, text: [`${max.toLocaleString("en")} jobs`, "Few"],
      textStyle: { color: INK, fontSize: 11 }, inRange: { color: ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"] }, outOfRange: { color: "#e6ebf3" },
    },
    geo: {
      map: "world", roam: true, scaleLimit: { min: 1, max: MAX_ZOOM }, top: 2, bottom: 2, left: 2, right: 2, selectedMode: false, nameProperty: "name", tooltip: { show: true },
      zoom: view.current.zoom, ...(view.current.center ? { center: view.current.center } : {}),
      itemStyle: { areaColor: "#e6ebf3", borderColor: "#fcfcfb", borderWidth: 0.6 },
      emphasis: { label: { show: false }, itemStyle: { areaColor: "#c8202f" } },
      regions: selected.map((code) => ({ name: code, itemStyle: { borderColor: "#c8202f", borderWidth: 1.5 } })),
    },
    series: [
      { type: "map", geoIndex: 0, data: rows.map((r) => ({ name: r.code, value: r.jobs })) },
      {
        type: "scatter", coordinateSystem: "geo", silent: false, animation: false, z: 5,
        symbolSize: (value: number[]) => 8 + 18 * Math.sqrt(value[2] / maxPlace),
        itemStyle: { color: "#eb6834", opacity: 0.9, borderColor: "#fcfcfb", borderWidth: 1 },
        emphasis: { scale: 1.2, itemStyle: { color: "#c8202f", opacity: 1 } },
        data: points.map((place) => ({ name: place.name, value: [place.lng, place.lat, place.jobs], place })),
      },
    ],
  };
  const ref = useChart(option, (p) => {
    if (p.seriesType === "scatter") { if (level !== "country") onPlace(p.data.place, level); }
    else if (names[p.name]) onPick(p.name);
  }, ready, chart);

  useEffect(() => {
    const instance = chart.current;
    if (!instance) return;
    const onRoam = () => {
      const geo = (instance.getOption() as any).geo?.[0];
      if (!geo) return;
      view.current = { zoom: geo.zoom ?? 1, center: geo.center ?? view.current.center };
      setLevel(levelFor(view.current.zoom));
    };
    instance.on("georoam", onRoam);
    return () => { instance.off("georoam", onRoam); };
  }, []);

  const zoomBy = (factor: number) => {
    const zoom = Math.min(MAX_ZOOM, Math.max(1, view.current.zoom * factor));
    view.current = { ...view.current, zoom };
    chart.current?.setOption({ geo: [{ zoom, ...(view.current.center ? { center: view.current.center } : {}) }] });
    setLevel(levelFor(zoom));
  };
  const reset = () => { view.current = { zoom: 1 }; setLevel("country"); redraw((n) => n + 1); };

  return (
    <>
    <div className="relative">
      <div ref={ref} className="h-[23rem] w-full" role="img" aria-label="World map of open jobs by country, with states and cities marked when zoomed in. The same numbers are in the tables on this page." />
      <div className="absolute right-1 top-1 flex flex-col gap-1">
        <button type="button" className="btn !h-8 !w-8 !p-0 justify-center" aria-label="Zoom in" title="Zoom in" onClick={() => zoomBy(2)}><Plus size={15} aria-hidden /></button>
        <button type="button" className="btn !h-8 !w-8 !p-0 justify-center" aria-label="Zoom out" title="Zoom out" onClick={() => zoomBy(0.5)}><Minus size={15} aria-hidden /></button>
        <button type="button" className="btn !h-8 !w-8 !p-0 justify-center" aria-label="Reset map" title="Reset map" onClick={reset}><RotateCcw size={14} aria-hidden /></button>
      </div>
    </div>
    <p className="mt-1.5 text-xs text-ink-2" aria-live="polite">{LEVEL_NOTE[level]}</p>
    </>
  );
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
