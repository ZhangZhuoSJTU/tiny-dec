import STAGES from "../data/stages";
import { highlightCode } from "../lib/highlighter";

const COMPACT_C = `/* tiny-dec output */
#include <stdint.h>

typedef struct agg_8 {
  int32_t field_0;
  int32_t field_4;
} agg_8;

static uint32_t main(void);
static uint32_t parse_record(agg_8* arg_x10_4, int32_t arg_x11_4);

static uint32_t main(void) {
  int32_t local_24_4, local_20_4, local_16_4, local_12_4;
  uint32_t call_0x11118_ret;
  local_12_4 = 20; local_16_4 = 2;
  local_20_4 = 10; local_24_4 = 1;
  call_0x11118_ret = parse_record(&local_24_4, 2);
  return call_0x11118_ret;
}

static uint32_t parse_record(agg_8* arg_x10_4, int32_t arg_x11_4) {
  int32_t local_24_4, local_20_4;
  local_20_4 = 0; local_24_4 = 0;
  while (local_24_4 <s arg_x11_4) {
    local_20_4 += arg_x10_4[local_24_4].field_0;
    local_20_4 += arg_x10_4[local_24_4].field_4;
    local_24_4 += 1;
  }
  return local_20_4;
}`;

import { useThemeFonts } from "../lib/theme";

export default function CompletionView() {
  const fonts = useThemeFonts();
  const rawBytes = STAGES[0].content;
  const trimmedBytes = rawBytes.split("\n").slice(0, 32).join("\n") + "\n  ...";

  return (
    <div style={{
      display: "flex", flexDirection: "column", alignItems: "center",
      justifyContent: "center",
      padding: "32px 24px", height: "100%", gap: 16,
    }}>
      <div className="reveal-stagger" style={{
        display: "flex", flexDirection: "column", alignItems: "center",
        gap: 14, width: "100%", maxWidth: 1100, textAlign: "center",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <img src="https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/1f389.svg" alt="" style={{ width: 32, height: 32 }} />
          <h2 style={{
            fontFamily: fonts.display, fontSize: 34, fontWeight: 700,
            letterSpacing: "-0.01em",
          }} className="gradient-text">
            Journey Complete!
          </h2>
          <img src="https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/2728.svg" alt="" style={{ width: 28, height: 28 }} />
        </div>
        <div style={{ display: "flex", gap: 16, width: "100%", marginTop: 6, alignItems: "center" }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{
              fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 700,
              color: "var(--fg-tertiary)", marginBottom: 6, textAlign: "left",
              textTransform: "uppercase", letterSpacing: "0.08em",
              display: "flex", alignItems: "center", gap: 4,
            }}>
              <img src="https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/1f4be.svg" alt="" style={{ width: 13, height: 13 }} />
              .text section (232 bytes)
            </div>
            <pre className="code-surface" style={{ opacity: 0.45, fontSize: 10, textAlign: "left", lineHeight: 1.5 }}>
<code>{trimmedBytes}</code></pre>
          </div>
          <div style={{
            display: "flex", flexDirection: "column", alignItems: "center",
            justifyContent: "center", gap: 4, padding: "0 8px", flexShrink: 0,
          }}>
            <img src="https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/1fa84.svg" alt="" style={{ width: 24, height: 24 }} />
            <div style={{
              width: 40, height: 3, borderRadius: 2,
              background: "linear-gradient(90deg, var(--phase-fe), var(--phase-an), var(--phase-be))",
            }} />
            <span style={{ fontSize: 18, color: "var(--fg-tertiary)" }}>&rarr;</span>
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{
              fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 700,
              color: "var(--fg-tertiary)", marginBottom: 6, textAlign: "left",
              textTransform: "uppercase", letterSpacing: "0.08em",
              display: "flex", alignItems: "center", gap: 4,
            }}>
              <img src="https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/1f4c4.svg" alt="" style={{ width: 13, height: 13 }} />
              Decompiled C
            </div>
            <pre className="code-surface" style={{ fontSize: 10, textAlign: "left", lineHeight: 1.5 }}>
<code>{highlightCode(COMPACT_C)}</code></pre>
          </div>
        </div>

        <div className="github-cta" style={{ marginTop: 6 }}>
          <a
            href="https://github.com/ZhangZhuoSJTU/tiny-dec"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              padding: "10px 20px", fontSize: 15, fontWeight: 700,
              color: "#fff", textDecoration: "none",
              display: "flex", alignItems: "center", gap: 8,
              background: "var(--pokeball-red)", borderRadius: 12,
              boxShadow: "var(--shadow-md)",
              transition: "transform 150ms, filter 150ms",
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
            View on GitHub
          </a>
          <span className="star-nudge">
            <span className="wave">&#x1F448;</span>
            check this repo out!
          </span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, marginTop: 6 }}>
          <p style={{ fontSize: 13, color: "var(--fg-secondary)", lineHeight: 1.6, fontWeight: 500 }}>
            <img src="https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/1f4dd.svg" alt="" style={{ width: 14, height: 14, verticalAlign: "middle", marginRight: 3 }} />
            An educational blog series is on the way, written together by{" "}
            <a href="https://zzhang.xyz" target="_blank" rel="noopener noreferrer" style={{ color: "var(--fg)", textDecoration: "underline", textUnderlineOffset: 3, fontWeight: 700 }}>Zhuo Zhang</a>,{" "}
            <a href="https://www.linkedin.com/in/hugo-matousek/" target="_blank" rel="noopener noreferrer" style={{ color: "var(--fg)", textDecoration: "underline", textUnderlineOffset: 3, fontWeight: 700 }}>Hugo Matousek</a>, and{" "}
            <a href="https://www.linkedin.com/in/seunghyun-sung/" target="_blank" rel="noopener noreferrer" style={{ color: "var(--fg)", textDecoration: "underline", textUnderlineOffset: 3, fontWeight: 700 }}>Seunghyun Sung</a>.
          </p>
          <a href="https://daplab.cs.columbia.edu/" target="_blank" rel="noopener noreferrer"
            style={{ display: "inline-flex", alignItems: "center" }}>
            <img src="https://daplab.cs.columbia.edu/files/images/daplab_logo_horiz.png" alt="DAPLab"
              style={{ height: 18, objectFit: "contain" }} />
          </a>
        </div>
      </div>
    </div>
  );
}
