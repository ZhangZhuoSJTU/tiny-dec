import STAGES, { PHASE_META, type Stage } from "../data/stages";
import { fontsFor, type ThemeMode } from "../lib/theme";

interface Props {
  current: number;
  visited: Set<number>;
  onGo: (index: number) => void;
  theme: ThemeMode;
}

const STAGE_EMOJIS: Record<string, string> = {
  "Start": "1f3c1",
  "Raw Bytes": "1f4be",
  "Loader": "1f4e6",
  "Instruction Decode": "1f9e9",
  "P-code Lift": "1f680",
  "Disassembly & CFG": "1f578-fe0f",
  "IR Containers": "1f4e6",
  "Simplify": "2702-fe0f",
  "Dataflow Analysis": "1f30a",
  "SSA Construction": "1f3d7-fe0f",
  "Call Analysis": "1f4de",
  "Stack Analysis": "1f4da",
  "Memory Analysis": "1f9e0",
  "Scalar Types": "1f522",
  "Aggregate Types": "1f9f1",
  "Variables": "1f3f7-fe0f",
  "Range Analysis": "1f4cf",
  "Interprocedural": "1f517",
  "Control Flow Structuring": "1f3db-fe0f",
  "C Lowering": "2b07-fe0f",
  "Final C": "1f4c4",
  "Complete": "2728",
};

const ALL_ENTRIES: { name: string; phase: Stage["phase"] | null; emoji: string }[] = [
  { name: "Start", phase: null, emoji: STAGE_EMOJIS["Start"] },
  ...STAGES.map((s) => ({ name: s.name, phase: s.phase, emoji: STAGE_EMOJIS[s.name] ?? "1f50d" })),
  { name: "Complete", phase: null, emoji: STAGE_EMOJIS["Complete"] },
];

function segColor(phase: Stage["phase"] | null, active: boolean, visited: boolean): string {
  const base = phase ? PHASE_META[phase].color : "rgba(100,70,30,0.15)";
  if (active) return base;
  if (visited) return base + "55";
  return "rgba(100,70,30,0.08)";
}

export default function ProgressBar({ current, visited, onGo, theme }: Props) {
  const fonts = fontsFor(theme);
  return (
    <div className="progress-bar" style={{ fontFamily: fonts.body }}>
      <span
        className="progress-wordmark"
        style={{ color: "var(--fg)", display: "flex", alignItems: "center", gap: 5, fontFamily: fonts.display, cursor: "pointer" }}
        onClick={() => onGo(0)}
        title="Back to start"
      >
        <img src="https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/1f50d.svg" alt="" style={{ width: 16, height: 16 }} />
        <span><span style={{ color: "var(--pokeball-red)" }}>tiny</span>-dec</span>
      </span>
      <div className="progress-track">
        {ALL_ENTRIES.map((entry, i) => {
          const isActive = i === current;
          const isVisited = visited.has(i);
          return (
            <button
              key={i}
              className={`progress-segment ${isActive ? "active" : ""}`}
              style={{
                background: segColor(entry.phase, isActive, isVisited),
                boxShadow: isActive ? `0 0 10px ${segColor(entry.phase, true, false)}50` : undefined,
              }}
              onClick={() => onGo(i)}
              aria-label={`Go to ${entry.name}`}
              title={entry.name}
            >
              {(isActive || isVisited) && (
                <img
                  src={`https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/${entry.emoji}.svg`}
                  alt=""
                  className="progress-segment-icon"
                  style={isVisited && !isActive ? { opacity: 0.5 } : undefined}
                />
              )}
            </button>
          );
        })}
      </div>
      <div className="progress-meta">
        <span className="progress-counter">
          {current}/{ALL_ENTRIES.length - 1}
        </span>
        <span className="progress-stage-name">{ALL_ENTRIES[current]?.name ?? ""}</span>
      </div>
    </div>
  );
}
