import type { PositionedEdge } from "../lib/graph-layout";

interface Props {
  edges: PositionedEdge[];
  phaseColor: string;
  isDataflow?: boolean;
}

function pointsToPath(points: { x: number; y: number }[]): string {
  if (points.length === 0) return "";
  const [first, ...rest] = points;
  let d = `M ${first.x} ${first.y}`;
  if (rest.length === 1) {
    d += ` L ${rest[0].x} ${rest[0].y}`;
  } else if (rest.length >= 2) {
    for (let i = 0; i < rest.length - 1; i++) {
      const curr = rest[i];
      const next = rest[i + 1];
      const midX = (curr.x + next.x) / 2;
      const midY = (curr.y + next.y) / 2;
      d += ` Q ${curr.x} ${curr.y} ${midX} ${midY}`;
    }
    const last = rest[rest.length - 1];
    d += ` L ${last.x} ${last.y}`;
  }
  return d;
}

export default function CFGEdges({ edges, phaseColor, isDataflow }: Props) {
  return (
    <svg style={{ position: "absolute", inset: 0, pointerEvents: "none", overflow: "visible" }}>
      <defs>
        <marker id="arrow" viewBox="0 0 10 8" refX="10" refY="4" markerWidth="7" markerHeight="5" orient="auto-start-reverse">
          <path d="M 0 0 L 10 4 L 0 8 z" fill="var(--fg-tertiary)" />
        </marker>
        <marker id="arrow-phase" viewBox="0 0 10 8" refX="10" refY="4" markerWidth="7" markerHeight="5" orient="auto-start-reverse">
          <path d="M 0 0 L 10 4 L 0 8 z" fill={phaseColor} />
        </marker>
        <marker id="arrow-dataflow" viewBox="0 0 10 8" refX="10" refY="4" markerWidth="7" markerHeight="5" orient="auto-start-reverse">
          <path d="M 0 0 L 10 4 L 0 8 z" fill="var(--accent)" />
        </marker>
      </defs>
      {edges.map((edge) => {
        const isBack = edge.type === "back";
        return (
          <g key={`${edge.source}-${edge.target}`}>
            <path
              d={pointsToPath(edge.points)}
              className={`cfg-edge ${isBack ? "back-edge" : ""}`}
              style={isBack ? { stroke: phaseColor } : undefined}
              markerEnd={isBack ? "url(#arrow-phase)" : "url(#arrow)"}
            />
            {isDataflow && !isBack && (
              <path
                d={pointsToPath(edge.points)}
                className="cfg-edge dataflow-edge"
                style={{ stroke: "var(--accent)" }}
                markerEnd="url(#arrow-dataflow)"
              />
            )}
            {edge.label && edge.points.length >= 2 && (() => {
              const mid = edge.points[Math.floor(edge.points.length / 2)];
              const prev = edge.points[Math.floor(edge.points.length / 2) - 1] ?? mid;
              const dx = mid.x - prev.x;
              const offsetX = dx >= 0 ? 10 : -10;
              return (
                <text
                  className="cfg-edge-label"
                  x={mid.x + offsetX}
                  y={mid.y - 6}
                  textAnchor={dx >= 0 ? "start" : "end"}
                >
                  {edge.label}
                </text>
              );
            })()}
          </g>
        );
      })}
    </svg>
  );
}
