import { useEffect, useRef } from "react";
import { renderInlineMarkdown } from "../lib/markdown";
import { useThemeFonts } from "../lib/theme";

interface Props {
  text: string;
  color: string;
  anchorRect: { top: number; left: number; width: number; height: number } | null;
  side: "left" | "right";
  stepLabel: string;
  onNext: () => void;
  onPrev: () => void;
}

export default function GuidedCallout({ text, color, anchorRect, side, stepLabel, onNext, onPrev }: Props) {
  const fonts = useThemeFonts();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.key === "ArrowRight" || e.key === " ") {
        e.preventDefault();
        e.stopPropagation();
        onNext();
      } else if (e.key === "ArrowLeft" || e.key === "Backspace" || e.key === "Delete") {
        e.preventDefault();
        e.stopPropagation();
        onPrev();
      }
    };
    window.addEventListener("keydown", handler, true);
    return () => window.removeEventListener("keydown", handler, true);
  }, [onNext, onPrev]);

  if (!anchorRect) return null;

  const top = anchorRect.top + anchorRect.height / 2;
  const left = side === "right"
    ? anchorRect.left + anchorRect.width + 12
    : anchorRect.left - 12;

  return (
    <div
      ref={ref}
      className="guided-callout"
      style={{
        position: "fixed",
        top,
        left,
        transform: side === "right" ? "translateY(-50%)" : "translateX(-100%) translateY(-50%)",
        zIndex: 9999,
      }}
    >
      <div className="guided-callout-connector" style={{
        position: "absolute",
        top: "50%",
        [side === "right" ? "left" : "right"]: -8,
        width: 8,
        height: 2,
        background: `${color}60`,
        transform: "translateY(-50%)",
      }} />
      <div className="guided-callout-card" style={{
        borderColor: `${color}40`,
        boxShadow: `0 0 16px ${color}10, var(--shadow-md)`,
      }}>
        <div className="guided-callout-badge" style={{ background: `${color}20`, color }}>
          {stepLabel}
        </div>
        <div className="guided-callout-text" style={{ fontFamily: fonts.body }}>{renderInlineMarkdown(text)}</div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button className="guided-callout-next" style={{ color: "var(--fg-tertiary)" }} onClick={onPrev}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ transform: "rotate(180deg)" }}>
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
            Back
          </button>
          <button className="guided-callout-next" style={{ color }} onClick={onNext}>
            Next
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
