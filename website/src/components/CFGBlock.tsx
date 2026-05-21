import { highlightLine } from "../lib/highlighter";
import type { DiffLine } from "../lib/cfg-differ";

interface Props {
  address: string;
  label?: string;
  lines: DiffLine[];
  phaseColor: string;
  style?: React.CSSProperties;
}

function stripCommonIndent(lines: DiffLine[]): DiffLine[] {
  const nonEmpty = lines.filter((l) => l.text.trim().length > 0);
  if (nonEmpty.length === 0) return lines;
  const minIndent = Math.min(...nonEmpty.map((l) => l.text.match(/^\s*/)?.[0].length ?? 0));
  if (minIndent === 0) return lines;
  return lines.map((l) => ({ ...l, text: l.text.slice(minIndent) }));
}

export default function CFGBlock({ address, label, lines, phaseColor, style }: Props) {
  const stripped = stripCommonIndent(lines);

  return (
    <div className="cfg-block" style={{ borderTop: `2px solid ${phaseColor}`, ...style }}>
      <div className="cfg-block-header" style={{ color: phaseColor }}>
        <span>{address}</span>
        {label && <span className="block-label">({label})</span>}
      </div>
      <div className="cfg-block-body">
        {stripped.map((line, i) => (
          <div key={i} className={`cfg-line ${line.type}`}>
            {highlightLine(line.text)}
          </div>
        ))}
      </div>
    </div>
  );
}
