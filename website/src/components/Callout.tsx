interface Props {
  x: number;
  y: number;
  color: string;
  children: React.ReactNode;
  side?: "left" | "right";
}

export default function Callout({ x, y, color, children, side = "right" }: Props) {
  const offset = side === "right" ? 12 : -12;
  return (
    <div style={{
      position: "absolute",
      left: side === "right" ? x + offset : undefined,
      right: side === "left" ? undefined : undefined,
      top: y,
      transform: side === "left" ? `translateX(calc(-100% + ${x + offset}px))` : undefined,
      ...(side === "left" ? { left: x + offset, transform: "translateX(-100%)" } : { left: x + offset }),
      zIndex: 10,
      pointerEvents: "none",
      animation: "callout-in 400ms cubic-bezier(0.16, 1, 0.3, 1) forwards",
      opacity: 0,
    }}>
      <div style={{
        background: `${color}15`,
        border: `1px solid ${color}40`,
        borderRadius: 4,
        padding: "3px 6px",
        fontFamily: "var(--font-mono)",
        fontSize: 9,
        lineHeight: 1.4,
        color: color,
        whiteSpace: "nowrap",
        boxShadow: `0 0 8px ${color}10`,
      }}>
        {children}
      </div>
      <style>{`
        @keyframes callout-in {
          from { opacity: 0; transform: ${side === "left" ? "translateX(-100%) translateY(4px)" : "translateY(4px)"}; }
          to { opacity: 1; transform: ${side === "left" ? "translateX(-100%) translateY(0)" : "translateY(0)"}; }
        }
      `}</style>
    </div>
  );
}
