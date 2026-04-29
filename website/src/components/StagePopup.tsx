import { useEffect } from "react";
import { PHASE_META } from "../data/stages";
import type { Phase } from "../data/stages";
import { renderInlineMarkdown } from "../lib/markdown";
import { useThemeFonts } from "../lib/theme";

interface Props {
  title: string;
  text: string;
  phase: Phase | null;
  onNext: () => void;
  onPrev: () => void;
}

export default function StagePopup({ title, text, phase, onNext, onPrev }: Props) {
  const fonts = useThemeFonts();
  const color = phase ? PHASE_META[phase].color : "var(--accent)";
  const paragraphs = text.split("\n\n").filter((p) => p.trim());

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.key === "ArrowRight" || e.key === " ") {
        e.preventDefault();
        e.stopImmediatePropagation();
        onNext();
      } else if (e.key === "ArrowLeft" || e.key === "Backspace" || e.key === "Delete") {
        e.preventDefault();
        e.stopImmediatePropagation();
        onPrev();
      }
    };
    window.addEventListener("keydown", handler, true);
    return () => window.removeEventListener("keydown", handler, true);
  }, [onNext, onPrev]);

  return (
    <div className="popup-overlay" onClick={onNext}>
      <div className="popup-card" onClick={(e) => e.stopPropagation()}>
        <div className="popup-accent" style={{ background: color }} />
        <div className="popup-body">
          <h2 className="popup-title" style={{ fontFamily: fonts.display }}>{title}</h2>
          <div className="popup-text" style={{ fontFamily: fonts.body }}>
            {paragraphs.map((p, i) => (
              <p key={i} style={{ marginBottom: i < paragraphs.length - 1 ? 14 : 0 }}>
                {renderInlineMarkdown(p)}
              </p>
            ))}
          </div>
          <button className="popup-next" style={{ background: color, fontFamily: fonts.body }} onClick={onNext}>
            Continue
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
