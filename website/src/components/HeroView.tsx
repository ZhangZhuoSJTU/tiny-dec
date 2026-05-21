import { useThemeFonts } from "../lib/theme";

export default function HeroView() {
  const fonts = useThemeFonts();
  return (
    <div style={{
      display: "flex", flexDirection: "column", alignItems: "center",
      justifyContent: "center", height: "100%", padding: "40px 32px",
      position: "relative", overflow: "hidden",
    }} className="noise-bg grid-bg">
      <div className="reveal-stagger" style={{
        display: "flex", flexDirection: "column", alignItems: "center", gap: 14,
        position: "relative", zIndex: 1,
      }}>
        {/* Pokeball decoration */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <img src="https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/2728.svg" alt="" style={{ width: 20, height: 20 }} />
          <div style={{
            fontFamily: fonts.display, fontWeight: 700, fontSize: 14,
            letterSpacing: "0.18em", textTransform: "uppercase",
            color: "var(--pokeball-red)",
          }}>
            Educational Decompiler
          </div>
          <img src="https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/2728.svg" alt="" style={{ width: 20, height: 20 }} />
        </div>

        <h1 style={{
          fontFamily: fonts.display, fontSize: 58, fontWeight: 700,
          letterSpacing: "-0.02em", lineHeight: 1, color: "var(--fg)",
          display: "flex", alignItems: "center", gap: 12,
        }}>
          <img src="https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/1f50d.svg" alt="" style={{ width: 42, height: 42 }} />
          tiny-dec
        </h1>

        <p style={{
          fontSize: 18, color: "var(--fg-secondary)", maxWidth: 500,
          lineHeight: 1.7, textAlign: "center", fontWeight: 500,
        }}>
          Watch 232 bytes of RISC-V machine code transform into readable C
          across 19 pipeline stages!
        </p>

        {/* Pipeline overview */}
        <div style={{
          display: "flex", alignItems: "center", gap: 6, marginTop: 4,
          padding: "10px 16px", borderRadius: 14,
          background: "var(--bg-elevated)", border: "2px solid var(--border)",
          boxShadow: "var(--shadow-md)",
        }}>
          <span style={{
            fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--fg-secondary)", fontWeight: 600,
          }}>
            <img src="https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/1f4be.svg" alt="" style={{ width: 14, height: 14, verticalAlign: "middle", marginRight: 4 }} />
            ELF
          </span>
          {([
            { label: "Frontend", count: 5, color: "var(--phase-fe)", emoji: "1f9e9" },
            { label: "Analysis", count: 11, color: "var(--phase-an)", emoji: "1f52c" },
            { label: "Backend", count: 3, color: "var(--phase-be)", emoji: "2699-fe0f" },
          ] as const).map((p) => (
            <span key={p.label} style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <span style={{ fontSize: 14, color: "var(--fg-tertiary)" }}>&rarr;</span>
              <span style={{
                fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 700,
                padding: "3px 10px", borderRadius: 10,
                background: `color-mix(in srgb, ${p.color} 12%, transparent)`,
                border: `2px solid color-mix(in srgb, ${p.color} 25%, transparent)`,
                color: p.color, letterSpacing: "0.04em",
                display: "flex", alignItems: "center", gap: 4,
              }}>
                <img src={`https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/${p.emoji}.svg`} alt="" style={{ width: 13, height: 13 }} />
                <span style={{ opacity: 0.6 }}>{p.count}</span>
                {p.label}
              </span>
            </span>
          ))}
          <span style={{ fontSize: 14, color: "var(--fg-tertiary)" }}>&rarr;</span>
          <span style={{
            fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--fg-secondary)", fontWeight: 600,
          }}>
            <img src="https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/1f4c4.svg" alt="" style={{ width: 14, height: 14, verticalAlign: "middle", marginRight: 4 }} />
            C
          </span>
        </div>

        {/* What you'll learn — with cute emoji icons */}
        <div style={{
          display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10,
          marginTop: 10, maxWidth: 540, width: "100%",
        }}>
          {([
            {
              emoji: "1f3ae",
              title: "Interactive",
              desc: "Step-by-step walkthrough with guided callouts",
              accent: "var(--water-blue)",
            },
            {
              emoji: "1f3af",
              title: "19 Stages",
              desc: "From raw bytes to C, every transformation visible",
              accent: "var(--ghost-purple)",
            },
            {
              emoji: "1fa84",
              title: "AI Tutor",
              desc: "Ask questions about any stage with built-in chat",
              accent: "var(--pokeball-red)",
            },
          ] as const).map((f) => (
            <div key={f.title} style={{
              padding: "14px 14px", borderRadius: 14,
              background: "var(--bg-elevated)", border: "2px solid var(--border)",
              textAlign: "left", boxShadow: "var(--shadow-sm)",
              transition: "transform 200ms, box-shadow 200ms",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.transform = "translateY(-2px)"; e.currentTarget.style.boxShadow = "var(--shadow-md)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.transform = ""; e.currentTarget.style.boxShadow = "var(--shadow-sm)"; }}
            >
              <img src={`https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/${f.emoji}.svg`} alt="" style={{ width: 24, height: 24, marginBottom: 8 }} />
              <div style={{ fontSize: 14, fontWeight: 700, color: "var(--fg)", marginBottom: 4 }}>{f.title}</div>
              <div style={{ fontSize: 12, color: "var(--fg-tertiary)", lineHeight: 1.5, fontWeight: 500 }}>{f.desc}</div>
            </div>
          ))}
        </div>

        {/* Author + Lab + GitHub */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 10 }}>
          <p style={{ fontSize: 15, color: "var(--fg-secondary)", fontWeight: 500 }}>
            by{" "}
            <a href="https://zzhang.xyz" target="_blank" rel="noopener noreferrer"
              style={{ color: "var(--pokeball-red)", textDecoration: "none", fontWeight: 700 }}>
              Zhuo Zhang
            </a>
          </p>
          <span style={{ width: 1, height: 16, background: "var(--border-strong)" }} />
          <a href="https://daplab.cs.columbia.edu/" target="_blank" rel="noopener noreferrer"
            style={{ display: "inline-flex", alignItems: "center" }}>
            <img src="https://daplab.cs.columbia.edu/files/images/daplab_logo_horiz.png" alt="DAPLab"
              style={{ height: 19, objectFit: "contain" }} />
          </a>
          <span style={{ width: 1, height: 16, background: "var(--border-strong)" }} />
          <div className="github-cta">
            <a
              href="https://github.com/ZhangZhuoSJTU/tiny-dec"
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: "inline-flex", alignItems: "center", gap: 6,
                padding: "6px 14px", borderRadius: 10,
                background: "var(--bg-elevated)", border: "2px solid var(--border-strong)",
                color: "var(--fg)", textDecoration: "none", fontSize: 14, fontWeight: 700,
                transition: "border-color 150ms, box-shadow 150ms",
                boxShadow: "var(--shadow-sm)",
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
              GitHub
            </a>
            <span className="star-nudge">
              <span className="wave">&#x1F448;</span>
              check this repo out!
            </span>
          </div>
        </div>

        {/* Inspired by */}
        <div style={{
          display: "flex", gap: 8, alignItems: "center", marginTop: 2,
        }}>
          <span style={{ fontSize: 13, color: "var(--fg-secondary)", fontWeight: 600 }}>
            <img src="https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/1f4a1.svg" alt="" style={{ width: 14, height: 14, verticalAlign: "middle", marginRight: 3 }} />
            Built on ideas from
          </span>
          {([
            { name: "angr", url: "https://github.com/angr/angr", color: "#c03020" },
            { name: "Ghidra", url: "https://github.com/NationalSecurityAgency/ghidra", color: "#b45309" },
            { name: "radare2", url: "https://github.com/radareorg/radare2", color: "#2b6cb0" },
          ] as const).map((tool) => (
            <a
              key={tool.name}
              href={tool.url}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: "inline-flex", alignItems: "center", gap: 5,
                padding: "4px 10px", borderRadius: 8,
                border: `2px solid ${tool.color}30`,
                background: `${tool.color}0a`,
                color: tool.color, textDecoration: "none", fontSize: 13, fontWeight: 700,
                transition: "border-color 150ms, background 150ms",
              }}
            >
              {tool.name}
            </a>
          ))}
        </div>

        {/* Begin hint */}
        <div style={{
          marginTop: 24, display: "flex", alignItems: "center", gap: 8,
          fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--fg-tertiary)", fontWeight: 600,
        }}>
          <img src="https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/1f449.svg" alt="" style={{ width: 18, height: 18 }} />
          <span>Press</span>
          <kbd style={{
            display: "inline-flex", alignItems: "center", justifyContent: "center",
            width: 26, height: 22, borderRadius: 6,
            background: "var(--bg-elevated)", border: "2px solid var(--border-strong)",
            fontSize: 13, color: "var(--fg)",
          }}>
            &rarr;
          </kbd>
          <span>to begin your journey!</span>
        </div>
      </div>
    </div>
  );
}
