"use client";

import { useEffect, useRef, useCallback } from "react";
import { createChart, type IChartApi, type ISeriesApi, type CandlestickData, type LineData, ColorType } from "lightweight-charts";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface CandleDataPoint {
  time: string; // YYYY-MM-DD or unix timestamp
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export interface LineDataPoint {
  time: string;
  value: number;
}

interface PriceChartProps {
  data: CandleDataPoint[] | LineDataPoint[];
  mode?: "candlestick" | "line" | "area";
  height?: number;
  title?: string;
  volumeData?: LineDataPoint[];
  markers?: Array<{
    time: string;
    position: "aboveBar" | "belowBar";
    color: string;
    shape: "arrowUp" | "arrowDown" | "circle";
    text: string;
  }>;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export function PriceChart({
  data,
  mode = "candlestick",
  height = 400,
  title,
  volumeData,
  markers,
}: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | ISeriesApi<"Line"> | ISeriesApi<"Area"> | null>(null);

  const initChart = useCallback(() => {
    if (!containerRef.current) return;

    // Clean up existing chart
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
      seriesRef.current = null;
    }

    const chart = createChart(containerRef.current, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#94a3b8",
        fontFamily: "var(--font-geist-sans), system-ui, sans-serif",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "#1e293b" },
        horzLines: { color: "#1e293b" },
      },
      crosshair: {
        mode: 0, // Normal
        vertLine: { color: "#475569", width: 1, style: 2, labelBackgroundColor: "#334155" },
        horzLine: { color: "#475569", width: 1, style: 2, labelBackgroundColor: "#334155" },
      },
      timeScale: {
        borderColor: "#334155",
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        borderColor: "#334155",
        scaleMargins: { top: 0.1, bottom: volumeData ? 0.25 : 0.05 },
      },
      handleScroll: true,
      handleScale: true,
    });

    chartRef.current = chart;

    // Main series
    if (mode === "candlestick") {
      const series = chart.addCandlestickSeries({
        upColor: "#10b981",
        downColor: "#ef4444",
        borderUpColor: "#10b981",
        borderDownColor: "#ef4444",
        wickUpColor: "#10b981",
        wickDownColor: "#ef4444",
      });
      series.setData(data as CandlestickData[]);
      seriesRef.current = series;

      if (markers && markers.length > 0) {
        series.setMarkers(markers.map(m => ({ ...m, time: m.time as unknown as CandlestickData["time"] })));
      }
    } else if (mode === "area") {
      const series = chart.addAreaSeries({
        lineColor: "#3b82f6",
        topColor: "rgba(59, 130, 246, 0.3)",
        bottomColor: "rgba(59, 130, 246, 0.02)",
        lineWidth: 2,
      });
      series.setData(data as LineData[]);
      seriesRef.current = series;
    } else {
      const series = chart.addLineSeries({
        color: "#3b82f6",
        lineWidth: 2,
      });
      series.setData(data as LineData[]);
      seriesRef.current = series;
    }

    // Volume histogram
    if (volumeData && volumeData.length > 0) {
      const volumeSeries = chart.addHistogramSeries({
        color: "#475569",
        priceFormat: { type: "volume" },
        priceScaleId: "volume",
      });
      chart.priceScale("volume").applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
      });
      volumeSeries.setData(volumeData.map(v => ({ time: v.time, value: v.value, color: "#47556950" })) as LineData[]);
    }

    chart.timeScale().fitContent();

    // Responsive
    const observer = new ResizeObserver(entries => {
      for (const entry of entries) {
        chart.applyOptions({ width: entry.contentRect.width });
      }
    });
    observer.observe(containerRef.current);

    return () => {
      observer.disconnect();
      chart.remove();
    };
  }, [data, mode, height, volumeData, markers]);

  useEffect(() => {
    const cleanup = initChart();
    return cleanup;
  }, [initChart]);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
      {title && (
        <div className="px-4 py-3 border-b border-slate-800">
          <h3 className="text-sm font-semibold text-white">{title}</h3>
        </div>
      )}
      <div ref={containerRef} className="w-full" />
    </div>
  );
}
