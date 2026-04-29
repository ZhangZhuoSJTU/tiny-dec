import { highlightCode, formatEncoding } from "../lib/highlighter";
import type { Stage } from "../data/stages";

interface Props {
  stage: Stage;
  prevStage?: Stage;
}

function parseStructuredContent(content: string, stageId: string): { sections: Section[] } | null {
  if (stageId === "raw") return null;
  if (stageId === "c") return null;

  const sections: Section[] = [];
  const lines = content.split("\n");

  if (stageId === "loader") {
    const kvPairs: { key: string; value: string; color?: string }[] = [];
    for (const line of lines) {
      const m = line.match(/^\s+([\w.]+):\s+(.*)/);
      if (m && !m[1].startsWith(".")) {
        kvPairs.push({ key: m[1], value: m[2] });
      }
    }
    sections.push({ type: "kv", title: "Binary Info", items: kvPairs });

    const sectionItems: { key: string; value: string }[] = [];
    for (const line of lines) {
      const m = line.match(/^\s+(\.\w+)\s+vaddr=(0x[\da-f]+)\s+size=(0x[\da-f]+)/);
      if (m) sectionItems.push({ key: m[1], value: `${m[2]}  size=${m[3]}` });
    }
    if (sectionItems.length) sections.push({ type: "kv", title: "Sections", items: sectionItems });
    return { sections };
  }

  if (stageId === "c_lowering") {
    const fns: { name: string; sig: string; body: string[] }[] = [];
    let currentFn: { name: string; sig: string; body: string[] } | null = null;
    let inBody = false;
    for (const line of lines) {
      const fnMatch = line.match(/function 0x[\da-f]+ name=(\w+)/);
      if (fnMatch) {
        if (currentFn) fns.push(currentFn);
        currentFn = { name: fnMatch[1], sig: "", body: [] };
        inBody = false;
        continue;
      }
      if (!currentFn) continue;
      if (line.includes("signature:") || line.includes("returns:") || line.includes("locals:")) continue;
      if (line.trim().startsWith("param ") || line.trim().startsWith("return ") || line.trim().startsWith("local ")) {
        if (currentFn.sig) currentFn.sig += ", ";
        currentFn.sig += line.trim();
        continue;
      }
      if (line.includes("body:") && !inBody) { inBody = true; continue; }
      if (inBody && line.trim()) {
        currentFn.body.push(line.trim());
      }
    }
    if (currentFn) fns.push(currentFn);
    if (fns.length > 0) {
      for (const fn of fns) {
        sections.push({ type: "function", title: fn.name, signature: fn.sig, body: fn.body });
      }
      return { sections };
    }
  }

  return null;
}

interface Section {
  type: "kv" | "function";
  title: string;
  items?: { key: string; value: string; color?: string }[];
  signature?: string;
  body?: string[];
}

function KVSection({ section }: { section: Section }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{
        fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 700,
        textTransform: "uppercase", letterSpacing: "0.1em",
        color: "var(--fg-tertiary)", marginBottom: 8, paddingBottom: 4,
        borderBottom: "1px solid var(--border)",
      }}>
        {section.title}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {section.items?.map((item, i) => (
          <div key={i} data-kv={item.key} style={{
            display: "flex", gap: 8, fontFamily: "var(--font-mono)", fontSize: 14,
            padding: "4px 8px", borderRadius: 4, background: "var(--bg-hover)",
          }}>
            <span style={{ color: "var(--fg-tertiary)", minWidth: 100 }}>{item.key}</span>
            <span style={{ color: item.color || "var(--fg)" }}>{item.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function FunctionSection({ section }: { section: Section }) {
  return (
    <div className="function-section" style={{
      marginBottom: 16, border: "1px solid var(--border-strong)",
      borderRadius: 6, overflow: "hidden", background: "var(--bg-elevated)",
    }}>
      <div style={{
        padding: "6px 10px", borderBottom: "1px solid var(--border)",
        background: "var(--bg-hover)", display: "flex", alignItems: "center", gap: 6,
      }}>
        <span style={{
          fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 600,
          color: "var(--syn-keyword)",
        }}>fn</span>
        <span style={{
          fontFamily: "var(--font-mono)", fontSize: 14, fontWeight: 600,
          color: "var(--fg)",
        }}>{section.title}</span>
      </div>
      <div style={{ padding: "8px 10px" }}>
        {section.body?.map((line, i) => (
          <div key={i} style={{
            fontFamily: "var(--font-mono)", fontSize: 13, lineHeight: 1.6,
            padding: "1px 4px",
          }}>
            {highlightCode(line)}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function TextPanel({ stage, prevStage }: Props) {
  const structured = parseStructuredContent(stage.content, stage.id);

  if (structured) {
    return (
      <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
        <div className="change-banner">
          <div style={{ width: 3, height: 16, borderRadius: 2, background: "var(--fg-tertiary)", flexShrink: 0 }} />
          <span style={{ color: "var(--fg-secondary)", fontWeight: 500, flex: 1 }}>{stage.name}</span>
        </div>
        <div style={{ flex: 1, overflow: "auto", padding: "24px 20px", display: "flex", justifyContent: "center" }}>
          <div style={{ maxWidth: 600, width: "100%" }}>
            {structured.sections.map((section, i) => (
              section.type === "kv" ? <KVSection key={i} section={section} />
              : <FunctionSection key={i} section={section} />
            ))}
          </div>
        </div>
      </div>
    );
  }

  // Fallback: decoded instructions, p-code, raw bytes, final C
  const isCode = stage.id === "c";
  const isRaw = stage.id === "raw";
  const isDecode = stage.id === "decode" || stage.id === "pcode";

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div className="change-banner">
        <div style={{ width: 3, height: 16, borderRadius: 2, background: "var(--fg-tertiary)", flexShrink: 0 }} />
        <span style={{ color: "var(--fg-secondary)", fontWeight: 500, flex: 1 }}>{stage.name}</span>
      </div>
      <div style={{ flex: 1, overflow: "auto", padding: "24px 20px", display: "flex", justifyContent: "center" }}>
        <div style={{ maxWidth: isDecode ? 800 : 700, width: "100%" }}>
          {isDecode ? (
            <InstructionTable content={stage.content} stageId={stage.id} />
          ) : isRaw ? (
            <RawBytesView content={stage.content} />
          ) : (
            <pre className="code-surface" style={{
              fontSize: isCode ? 13 : 12,
              lineHeight: isCode ? 1.7 : 1.6,
            }}>
              <code>{highlightCode(stage.content)}</code>
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}

function RawBytesView({ content }: { content: string }) {
  const lines = content.split("\n");
  // .text section: file offsets 0xe4 to 0x1cc (vaddr 0x110e4, size 0xe8)
  const textStart = 0xe4;
  const textEnd = 0xe4 + 0xe8;

  const regions: { label: string | null; lines: string[]; id: string }[] = [];
  let current: typeof regions[0] | null = null;

  for (const line of lines) {
    const m = line.match(/^0x([0-9a-f]+)/);
    const offset = m ? parseInt(m[1], 16) : -1;
    const lineEnd = offset + 16;
    const isText = offset >= 0 && offset < textEnd && lineEnd > textStart;
    const regionId = isText ? "text" : "other";

    if (!current || current.id !== regionId) {
      if (current) regions.push(current);
      current = { label: isText ? ".text (executable code)" : null, lines: [], id: regionId };
    }
    current.lines.push(line);
  }
  if (current) regions.push(current);

  return (
    <pre className="code-surface" style={{ fontSize: 13.5, lineHeight: 1.6 }}>
      <code>
        {regions.map((region, i) =>
          region.id === "text" ? (
            <span key={i} className="raw-text-section" data-section="text" style={{
              display: "block",
              background: "rgba(96, 165, 250, 0.06)",
              borderLeft: "3px solid var(--phase-fe)",
              paddingLeft: 8,
              marginLeft: -11,
              borderRadius: 2,
            }}>
              <span style={{
                display: "block", fontSize: 11, fontWeight: 700,
                textTransform: "uppercase", letterSpacing: "0.08em",
                color: "var(--phase-fe)", opacity: 0.7,
                marginBottom: 2, userSelect: "none",
              }}>{region.label}</span>
              {region.lines.join("\n")}
            </span>
          ) : (
            <span key={i} style={{ display: "block", opacity: 0.5 }}>
              {region.lines.join("\n")}
            </span>
          )
        )}
      </code>
    </pre>
  );
}

function InstructionTable({ content, stageId }: { content: string; stageId: string }) {
  const lines = content.split("\n").filter((l) => l.trim());
  const isPcode = stageId === "pcode";

  const entries: { addr: string; encoding: string; asm: string; pcode: string[] }[] = [];
  let current: typeof entries[0] | null = null;

  for (const line of lines) {
    const instrMatch = line.match(/^\s*(0x[\da-f]+):\s+(0x[\da-f]+)\s+(.+)/);
    if (instrMatch) {
      if (current) entries.push(current);
      current = { addr: instrMatch[1], encoding: instrMatch[2], asm: instrMatch[3].trim(), pcode: [] };
    } else if (current && isPcode && line.trim()) {
      current.pcode.push(line.trim());
    }
  }
  if (current) entries.push(current);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {entries.map((entry, i) => (
        <div key={i} data-addr={entry.addr} style={{
          display: "flex", gap: 0, fontFamily: "var(--font-mono)", fontSize: 13,
          border: "1px solid var(--border)", borderRadius: 4, overflow: "hidden",
          background: "var(--bg-elevated)",
        }}>
          <div style={{
            padding: "4px 6px", color: "var(--syn-address)", fontSize: 12,
            borderRight: "1px solid var(--border)", minWidth: 80,
            background: "var(--bg-hover)",
          }}>
            {entry.addr}
          </div>
          <div style={{ flex: 1, padding: "4px 8px" }}>
            <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
              <span style={{ color: "var(--fg-tertiary)", fontSize: 12 }}>{formatEncoding(entry.encoding)}</span>
              <span style={{ color: "var(--fg)" }}>{highlightCode(entry.asm)}</span>
            </div>
            {entry.pcode.length > 0 && (
              <div style={{
                marginTop: 2, paddingTop: 2, borderTop: "1px dashed var(--border)",
                color: "var(--syn-opcode)", fontSize: 12, lineHeight: 1.5,
              }}>
                {entry.pcode.map((p, j) => (
                  <div key={j}>{highlightCode(p)}</div>
                ))}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
