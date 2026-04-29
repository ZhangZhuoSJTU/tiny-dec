import type { Stage } from "../data/stages";

interface Props {
  stage: Stage;
  fn: "main" | "parse_record";
}

interface SlotVisual {
  offset: number;
  size: number;
  role: string;
  varName?: string;
  typeName?: string;
  range?: string;
  isNew?: boolean;
}

interface StructField {
  offset: number;
  size: number;
  type: string;
}

interface AnalysisState {
  slots: SlotVisual[];
  aggregate?: { name: string; fields: StructField[] };
  prototype?: { params: string[]; ret: string };
  dataflowFact?: string;
}

const ANALYSIS_ORDER = ["dataflow", "ssa", "calls", "stack", "memory", "scalar_types", "aggregate_types", "variables", "range", "interproc"];

function buildAnalysisState(currentStageId: string, fnName: string): AnalysisState {
  const state: AnalysisState = { slots: [] };
  let idx = ANALYSIS_ORDER.indexOf(currentStageId);
  if (idx < 0) {
    if (currentStageId === "structuring") {
      idx = ANALYSIS_ORDER.length - 1;
    } else {
      return state;
    }
  }

  const isPR = fnName === "parse_record";

  if (idx >= ANALYSIS_ORDER.indexOf("dataflow")) {
    state.dataflowFact = isPR
      ? "x10 = 0x0 (entry block)"
      : "single block — no propagation needed";
  }

  if (idx >= ANALYSIS_ORDER.indexOf("stack")) {
    if (isPR) {
      state.slots = [
        { offset: -4, size: 4, role: "saved" },
        { offset: -8, size: 4, role: "saved" },
        { offset: -12, size: 4, role: "arg" },
        { offset: -16, size: 4, role: "arg" },
        { offset: -20, size: 4, role: "local" },
        { offset: -24, size: 4, role: "local" },
      ];
    } else {
      state.slots = [
        { offset: -4, size: 4, role: "saved" },
        { offset: -8, size: 4, role: "saved" },
        { offset: -12, size: 4, role: "local" },
        { offset: -16, size: 4, role: "local" },
        { offset: -20, size: 4, role: "local" },
        { offset: -24, size: 4, role: "local" },
      ];
    }
  }

  if (idx >= ANALYSIS_ORDER.indexOf("scalar_types")) {
    for (const slot of state.slots) {
      if (slot.role === "saved") slot.typeName = "word32";
      else if (slot.role === "arg" && slot.offset === -12 && isPR) slot.typeName = "ptr";
      else slot.typeName = "int32";
    }
  }

  if (idx >= ANALYSIS_ORDER.indexOf("aggregate_types") && isPR) {
    state.aggregate = {
      name: "agg_8",
      fields: [
        { offset: 0, size: 4, type: "int32" },
        { offset: 4, size: 4, type: "int32" },
      ],
    };
    const ptrSlot = state.slots.find((s) => s.offset === -12);
    if (ptrSlot) ptrSlot.typeName = "agg_8*";
  }

  if (idx >= ANALYSIS_ORDER.indexOf("variables")) {
    if (isPR) {
      const map: Record<number, string> = { [-12]: "arg_x10", [-16]: "arg_x11", [-20]: "sum", [-24]: "i" };
      for (const slot of state.slots) {
        if (map[slot.offset]) slot.varName = map[slot.offset];
      }
    } else {
      const map: Record<number, string> = { [-12]: "local_12", [-16]: "local_16", [-20]: "local_20", [-24]: "local_24" };
      for (const slot of state.slots) {
        if (map[slot.offset]) slot.varName = map[slot.offset];
      }
    }
  }

  if (idx >= ANALYSIS_ORDER.indexOf("range")) {
    if (isPR) {
      const ranges: Record<number, string> = { [-20]: "[0, 0]", [-24]: "[0, +∞)" };
      for (const slot of state.slots) {
        if (ranges[slot.offset]) slot.range = ranges[slot.offset];
      }
    } else {
      const ranges: Record<number, string> = { [-12]: "[20]", [-16]: "[2]", [-20]: "[10]", [-24]: "[1]" };
      for (const slot of state.slots) {
        if (ranges[slot.offset]) slot.range = ranges[slot.offset];
      }
    }
  }

  if (idx >= ANALYSIS_ORDER.indexOf("interproc")) {
    if (isPR) {
      state.prototype = { params: ["agg_8* arg_x10", "int32 arg_x11"], ret: "int32" };
    } else {
      state.prototype = { params: [], ret: "int32" };
    }
  }

  // Mark what's new at this stage
  const newStage = currentStageId;
  if (newStage === "stack") {
    for (const s of state.slots) s.isNew = true;
  }
  if (newStage === "scalar_types") {
    for (const s of state.slots) if (s.typeName) s.isNew = true;
  }
  if (newStage === "aggregate_types") {
    const ptrSlot = state.slots.find((s) => s.offset === -12 && isPR);
    if (ptrSlot) ptrSlot.isNew = true;
  }
  if (newStage === "variables") {
    for (const s of state.slots) if (s.varName) s.isNew = true;
  }
  if (newStage === "range") {
    for (const s of state.slots) if (s.range) s.isNew = true;
  }

  return state;
}

function roleColor(role: string): string {
  if (role === "saved") return "var(--phase-be)";
  if (role === "arg") return "var(--phase-fe)";
  return "var(--phase-an)";
}

function roleLabel(role: string, offset: number, isPR: boolean): string {
  if (role === "saved") return offset === -4 ? "saved ra" : "saved s0";
  if (role === "arg") return isPR ? (offset === -12 ? "arg x10" : "arg x11") : "";
  return "local";
}

export default function AnalysisPanel({ stage, fn }: Props) {
  const isPR = fn === "parse_record";
  const state = buildAnalysisState(stage.id, fn);

  if (state.slots.length === 0 && !state.dataflowFact && !state.prototype) return null;

  return (
    <div className="analysis-panel">
      <div className="analysis-panel-header">
        <span style={{ width: 6, height: 6, borderRadius: 3, background: "var(--phase-an)" }} />
        Analysis
      </div>
      <div className="analysis-panel-body">
        {/* Dataflow fact */}
        {state.dataflowFact && (
          <div style={{
            marginBottom: 12, padding: "4px 8px", borderRadius: 4,
            border: "1px solid var(--accent)",
            background: "rgba(245,158,11,0.06)",
            fontFamily: "var(--font-mono)", fontSize: 12,
            color: "var(--accent)",
            animation: stage.id === "dataflow" ? "callout-fade 600ms ease" : undefined,
          }}>
            <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--fg-tertiary)", marginBottom: 2 }}>propagated</div>
            {state.dataflowFact}
          </div>
        )}

        {/* Stack frame diagram */}
        {state.slots.length > 0 && (
          <div>
            <div style={{
              fontSize: 10, fontWeight: 700, textTransform: "uppercase",
              letterSpacing: "0.1em", color: "var(--fg-tertiary)", marginBottom: 4,
            }}>
              Stack Frame — 32B
            </div>
            <div style={{
              border: "2px solid var(--border-strong)", borderRadius: 8,
              overflow: "hidden", fontFamily: "var(--font-mono)", fontSize: 12,
              boxShadow: "var(--shadow-sm)",
            }}>
              {state.slots.map((slot, i) => (
                <div key={i} style={{
                  display: "flex", alignItems: "stretch",
                  borderBottom: i < state.slots.length - 1 ? "1px solid var(--border)" : "none",
                  background: slot.isNew ? `${roleColor(slot.role)}08` : "transparent",
                  transition: "background 400ms",
                }}>
                  {/* Offset */}
                  <div style={{
                    width: 36, padding: "3px 4px", textAlign: "right",
                    color: "var(--fg-tertiary)", borderRight: "1px solid var(--border)",
                    fontSize: 11, flexShrink: 0,
                  }}>
                    {slot.offset}
                  </div>
                  {/* Color bar */}
                  <div style={{
                    width: 4, background: roleColor(slot.role), flexShrink: 0,
                  }} />
                  {/* Content */}
                  <div style={{
                    flex: 1, padding: "3px 6px", minWidth: 0,
                    display: "flex", flexDirection: "column", gap: 1,
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                      <span style={{ color: "var(--fg-secondary)", fontSize: 11 }}>
                        {roleLabel(slot.role, slot.offset, isPR)}
                      </span>
                      {slot.varName && (
                        <span style={{
                          color: "var(--phase-be)", fontWeight: 600,
                          animation: slot.isNew && stage.id === "variables" ? "callout-fade 600ms ease" : undefined,
                        }}>
                          {slot.varName}
                        </span>
                      )}
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 4, flexWrap: "wrap" }}>
                      {slot.typeName && (
                        <span style={{
                          padding: "0 3px", borderRadius: 2, fontSize: 11,
                          background: slot.typeName === "agg_8*" ? "rgba(91,156,245,0.12)" : "rgba(94,234,212,0.1)",
                          color: slot.typeName === "agg_8*" ? "var(--phase-fe)" : "var(--syn-type)",
                          animation: slot.isNew && (stage.id === "scalar_types" || stage.id === "aggregate_types") ? "callout-fade 600ms ease" : undefined,
                        }}>
                          {slot.typeName}
                        </span>
                      )}
                      {slot.range && (
                        <span style={{
                          padding: "0 3px", borderRadius: 2, fontSize: 11,
                          background: "rgba(245,158,11,0.1)", color: "var(--accent)",
                          animation: slot.isNew && stage.id === "range" ? "callout-fade 600ms ease" : undefined,
                        }}>
                          {slot.range}
                        </span>
                      )}
                    </div>
                  </div>
                  {/* Size */}
                  <div style={{
                    padding: "3px 4px", color: "var(--fg-tertiary)", fontSize: 11,
                    display: "flex", alignItems: "center",
                  }}>
                    {slot.size}B
                  </div>
                </div>
              ))}
            </div>

            {/* Legend */}
            <div style={{
              marginTop: 6, display: "flex", gap: 8, fontSize: 10,
              fontFamily: "var(--font-mono)", color: "var(--fg-tertiary)",
            }}>
              <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
                <span style={{ width: 6, height: 6, borderRadius: 3, background: "var(--phase-an)" }} />local
              </span>
              <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
                <span style={{ width: 6, height: 6, borderRadius: 3, background: "var(--phase-be)" }} />saved
              </span>
              <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
                <span style={{ width: 6, height: 6, borderRadius: 3, background: "var(--phase-fe)" }} />arg
              </span>
            </div>
          </div>
        )}

        {/* Aggregate struct diagram */}
        {state.aggregate && (
          <div style={{ marginTop: 12 }}>
            <div style={{
              fontSize: 10, fontWeight: 700, textTransform: "uppercase",
              letterSpacing: "0.1em", color: "var(--fg-tertiary)", marginBottom: 4,
            }}>
              Discovered Struct
            </div>
            <div style={{
              border: "1px solid var(--phase-fe)",
              borderRadius: 4, overflow: "hidden",
              fontFamily: "var(--font-mono)", fontSize: 12,
              background: "rgba(91,156,245,0.04)",
              animation: stage.id === "aggregate_types" ? "callout-fade 600ms ease" : undefined,
            }}>
              <div style={{
                padding: "4px 8px", borderBottom: "1px solid var(--border)",
                background: "rgba(91,156,245,0.08)", color: "var(--phase-fe)",
                fontWeight: 600,
              }}>
                struct {state.aggregate.name}
              </div>
              {state.aggregate.fields.map((f, i) => (
                <div key={i} style={{
                  padding: "3px 8px", display: "flex", gap: 6,
                  borderBottom: i < state.aggregate!.fields.length - 1 ? "1px solid var(--border)" : "none",
                }}>
                  <span style={{ color: "var(--fg-tertiary)", fontSize: 11 }}>+{f.offset}</span>
                  <span style={{ color: "var(--syn-type)" }}>{f.type}</span>
                  <span style={{ color: "var(--fg-secondary)" }}>f{f.offset}</span>
                  <span style={{ color: "var(--fg-tertiary)", fontSize: 11 }}>{f.size}B</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Function prototype (last = newest at bottom) */}
        {state.prototype && (
          <div style={{
            marginTop: 12, padding: "6px 8px", borderRadius: 4,
            background: "var(--bg-hover)", border: "1px solid var(--border-strong)",
            fontFamily: "var(--font-mono)", fontSize: 12,
            animation: stage.id === "interproc" ? "callout-fade 600ms ease" : undefined,
          }}>
            <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--fg-tertiary)", marginBottom: 2 }}>prototype</div>
            <div style={{ color: "var(--syn-type)", marginBottom: 2 }}>{state.prototype.ret}</div>
            <div style={{ color: "var(--fg)", fontWeight: 600 }}>{fn}(</div>
            {state.prototype.params.map((p, i) => (
              <div key={i} style={{ color: "var(--fg-secondary)", paddingLeft: 8 }}>{p}{i < state.prototype!.params.length - 1 ? "," : ""}</div>
            ))}
            <div style={{ color: "var(--fg)", fontWeight: 600 }}>)</div>
          </div>
        )}

        <style>{`
          @keyframes callout-fade {
            from { opacity: 0; transform: translateY(4px); }
            to { opacity: 1; transform: translateY(0); }
          }
        `}</style>
      </div>
    </div>
  );
}
