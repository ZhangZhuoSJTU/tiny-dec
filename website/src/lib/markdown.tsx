import React from "react";

export function renderInlineMarkdown(text: string): React.ReactNode[] {
  const result: React.ReactNode[] = [];
  const regex = /(`[^`]+`|\*\*[^*]+\*\*)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      result.push(text.slice(lastIndex, match.index));
    }

    const token = match[0];
    if (token.startsWith("`")) {
      result.push(
        <code key={key++} style={{
          fontFamily: "var(--font-mono)", fontSize: "0.9em",
          background: "rgba(255,255,255,0.06)", padding: "1px 4px",
          borderRadius: 3, color: "var(--accent)",
        }}>
          {token.slice(1, -1)}
        </code>
      );
    } else {
      result.push(
        <strong key={key++} style={{ color: "var(--fg)", fontWeight: 600 }}>
          {token.slice(2, -2)}
        </strong>
      );
    }

    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    result.push(text.slice(lastIndex));
  }

  return result;
}
