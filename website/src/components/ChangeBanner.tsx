import type { DiffLine } from "../lib/cfg-differ";

interface Props {
  blockDiffs: Map<string, DiffLine[]>;
  phaseColor: string;
  stageName: string;
  stageDescription: string;
}

export default function ChangeBanner({ blockDiffs, phaseColor, stageName, stageDescription }: Props) {
  let added = 0;
  let modified = 0;
  let removed = 0;
  for (const lines of blockDiffs.values()) {
    for (const l of lines) {
      if (l.type === "added") added++;
      else if (l.type === "modified") modified++;
      else if (l.type === "removed") removed++;
    }
  }
  const total = added + modified + removed;

  return (
    <div className="change-banner">
      <div style={{
        width: 3, height: 16, borderRadius: 2, background: phaseColor, flexShrink: 0,
      }} />
      <span style={{ color: "var(--fg-secondary)", fontWeight: 500, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {stageName}
      </span>
      {total > 0 ? (
        <>
          {added > 0 && (
            <span className="change-stat">
              <span className="dot" style={{ background: "var(--diff-added-border)" }} />
              <span style={{ color: "var(--diff-added-border)" }}>+{added}</span>
            </span>
          )}
          {modified > 0 && (
            <span className="change-stat">
              <span className="dot" style={{ background: "var(--diff-modified-border)" }} />
              <span style={{ color: "var(--diff-modified-border)" }}>~{modified}</span>
            </span>
          )}
          {removed > 0 && (
            <span className="change-stat">
              <span className="dot" style={{ background: "var(--diff-removed-border)" }} />
              <span style={{ color: "var(--diff-removed-border)" }}>-{removed}</span>
            </span>
          )}
        </>
      ) : (
        <span style={{ color: "var(--fg-tertiary)", fontSize: 11 }}>no IR changes</span>
      )}
    </div>
  );
}
