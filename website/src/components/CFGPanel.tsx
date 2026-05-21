import { useEffect, useMemo, useRef, useState } from "react";
import type { Stage } from "../data/stages";
import { PHASE_META } from "../data/stages";
import { computeLayout } from "../lib/graph-layout";
import { diffCFG, type DiffLine } from "../lib/cfg-differ";
import CFGBlock from "./CFGBlock";
import CFGEdges from "./CFGEdges";
import ChangeBanner from "./ChangeBanner";
import AnalysisPanel from "./AnalysisPanel";
import CFGMinimap from "./CFGMinimap";

interface Props {
  stage: Stage;
  prevStage?: Stage;
}

type FnKey = "main" | "parse_record";

const ANALYSIS_STAGES = new Set([
  "dataflow", "ssa", "calls", "stack", "memory",
  "scalar_types", "aggregate_types", "variables", "range", "interproc",
  "structuring",
]);

function estimateNodeSize(block: { ir: string }): { width: number; height: number } {
  const irLines = block.ir.split("\n").filter((l) => l.trim());
  const maxLen = Math.max(...irLines.map((l) => l.trimStart().length), 8);
  const width = Math.min(700, Math.max(280, maxLen * 8.0 + 40));
  const height = irLines.length * 19 + 48;
  return { width, height };
}


export default function CFGPanel({ stage, prevStage }: Props) {
  const [fn, setFn] = useState<FnKey>("parse_record");
  const viewportRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: Event) => {
      const target = (e as CustomEvent).detail as FnKey;
      if (target === "main" || target === "parse_record") {
        setFn(target);
      }
    };
    window.addEventListener("walkthrough-fn", handler);
    return () => window.removeEventListener("walkthrough-fn", handler);
  }, []);

  const cfg = stage.cfg?.[fn];
  const prevCfg = prevStage?.cfg?.[fn];
  const phaseColor = PHASE_META[stage.phase].color;
  const hasAnalysisPanel = ANALYSIS_STAGES.has(stage.id);
  const showFancyEdges = true;


  const nodeWidths = useMemo(() => {
    if (!cfg) return new Map<string, number>();
    return new Map(cfg.blocks.map((b) => [b.address, estimateNodeSize(b).width]));
  }, [cfg]);

  const nodeHeights = useMemo(() => {
    if (!cfg) return new Map<string, number>();
    return new Map(cfg.blocks.map((b) => [b.address, estimateNodeSize(b).height]));
  }, [cfg]);

  const layout = useMemo(() => {
    if (!cfg) return null;
    return computeLayout(cfg.blocks, cfg.edges, nodeWidths, nodeHeights);
  }, [cfg, nodeWidths, nodeHeights]);

  const blockDiffs = useMemo(() => {
    if (!cfg) return new Map<string, DiffLine[]>();
    if (prevCfg) {
      const diffs = diffCFG(prevCfg.blocks, cfg.blocks);
      return new Map(diffs.map((d) => [d.address, d.lines]));
    }
    return new Map(
      cfg.blocks.map((b) => [
        b.address,
        b.ir.split("\n").filter((l) => l.trim()).map((l) => ({ type: "unchanged" as const, text: l })),
      ]),
    );
  }, [cfg, prevCfg]);

  if (!cfg || !layout) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "var(--fg-tertiary)" }}>
        No CFG data for this stage.
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, borderBottom: "1px solid var(--border)", flexShrink: 0 }}>
        <div style={{ display: "flex", gap: 4, padding: "6px 12px", borderRight: "1px solid var(--border)" }}>
          {(["main", "parse_record"] as const).map((key) => (
            <button
              key={key}
              onClick={() => {
                setFn(key);
                window.dispatchEvent(new CustomEvent("cfg-fn-changed", { detail: key }));
              }}
              style={{
                padding: "4px 10px", borderRadius: 4,
                border: fn === key ? `1px solid ${phaseColor}50` : "1px solid transparent",
                background: fn === key ? `${phaseColor}12` : "transparent",
                color: fn === key ? phaseColor : "var(--fg-tertiary)",
                fontFamily: "var(--font-mono)", fontSize: 13,
                fontWeight: fn === key ? 600 : 400,
                cursor: "pointer", transition: "all 120ms",
              }}
            >{key}</button>
          ))}
        </div>
        <ChangeBanner blockDiffs={blockDiffs} phaseColor={phaseColor} stageName={stage.name} stageDescription={stage.description} />
      </div>

      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Analysis panel on left */}
        {hasAnalysisPanel && <AnalysisPanel stage={stage} fn={fn} />}

        {/* Graph viewport */}
        <div ref={viewportRef} style={{ flex: 1, overflow: "auto", position: "relative" }}>
          <div style={{ position: "relative", width: layout.width + 200, height: layout.height, margin: "1rem auto", minWidth: layout.width + 200 }}>
            <CFGEdges edges={layout.edges} phaseColor={phaseColor} isDataflow={showFancyEdges} />
            {layout.nodes.map((node) => (
                <CFGBlock
                  key={node.address}
                  address={node.address}
                  label={node.label}
                  lines={blockDiffs.get(node.address) ?? []}
                  phaseColor={phaseColor}
                  style={{
                    position: "absolute",
                    left: node.x,
                    top: node.y,
                    width: node.width,
                  }}
                />
            ))}

            {/* Structure region overlays */}
            {cfg.regions?.map((region, ri) => {
              const regionNodes = region.blocks
                .map((addr) => layout.nodes.find((n) => n.address === addr))
                .filter(Boolean) as typeof layout.nodes;
              if (regionNodes.length === 0) return null;
              const pad = 12;
              const minX = Math.min(...regionNodes.map((n) => n.x)) - pad;
              const minY = Math.min(...regionNodes.map((n) => n.y)) - pad - 18;
              const maxX = Math.max(...regionNodes.map((n) => n.x + n.width)) + pad;
              const maxY = Math.max(...regionNodes.map((n) => n.y + n.height)) + pad;
              return (
                <div key={`region-${ri}`} style={{
                  position: "absolute",
                  left: minX, top: minY,
                  width: maxX - minX, height: maxY - minY,
                  border: `2px dashed ${region.color}60`,
                  borderRadius: 8,
                  background: `${region.color}08`,
                  pointerEvents: "none",
                  zIndex: 0,
                  animation: "callout-fade 600ms ease",
                }}>
                  <div style={{
                    position: "absolute",
                    top: 2, left: 8,
                    fontFamily: "var(--font-mono)",
                    fontSize: 12,
                    fontWeight: 600,
                    color: region.color,
                    opacity: 0.8,
                  }}>
                    {region.label}
                  </div>
                </div>
              );
            })}

          </div>
          {/* Minimap */}
          {layout.nodes.length > 2 && (
            <CFGMinimap
              nodes={layout.nodes}
              edges={layout.edges}
              layoutWidth={layout.width}
              layoutHeight={layout.height}
              phaseColor={phaseColor}
              viewportRef={viewportRef}
            />
          )}
        </div>
      </div>
    </div>
  );
}
