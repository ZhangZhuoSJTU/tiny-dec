import type { PositionedNode, PositionedEdge } from "../lib/graph-layout";

interface Props {
  nodes: PositionedNode[];
  edges: PositionedEdge[];
  layoutWidth: number;
  layoutHeight: number;
  phaseColor: string;
  viewportRef: React.RefObject<HTMLDivElement | null>;
}

export default function CFGMinimap({ nodes, edges, layoutWidth, layoutHeight, phaseColor, viewportRef }: Props) {
  const mapW = 140;
  const mapH = 100;
  const scaleX = mapW / Math.max(layoutWidth + 200, 1);
  const scaleY = mapH / Math.max(layoutHeight, 1);
  const scale = Math.min(scaleX, scaleY);

  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!viewportRef.current) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = (e.clientX - rect.left) / scale;
    const clickY = (e.clientY - rect.top) / scale;
    viewportRef.current.scrollTo({
      left: clickX - viewportRef.current.clientWidth / 2,
      top: clickY - viewportRef.current.clientHeight / 2,
      behavior: "smooth",
    });
  };

  return (
    <div className="cfg-minimap" onClick={handleClick}>
      <svg width={mapW} height={mapH} style={{ display: "block" }}>
        {edges.map((edge, i) => {
          if (edge.points.length < 2) return null;
          const pts = edge.points.map(p => `${p.x * scale},${p.y * scale}`).join(" ");
          return (
            <polyline
              key={i}
              points={pts}
              fill="none"
              stroke={edge.type === "back" ? phaseColor : "var(--fg-tertiary)"}
              strokeWidth={0.8}
            />
          );
        })}
        {nodes.map((node) => (
          <rect
            key={node.address}
            x={node.x * scale}
            y={node.y * scale}
            width={Math.max(node.width * scale, 3)}
            height={Math.max(node.height * scale, 2)}
            fill={`${phaseColor}30`}
            stroke={`${phaseColor}60`}
            strokeWidth={0.5}
            rx={1}
          />
        ))}
      </svg>
    </div>
  );
}
