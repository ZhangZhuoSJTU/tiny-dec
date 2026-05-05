import { useCallback, useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import STAGES, { PHASE_META } from "../data/stages";
import WALKTHROUGHS from "../data/walkthrough";
import { type AIMessage, type Provider, getModels, getStoredConfig, storeConfig, clearConfig, streamChat, isProviderBlocked } from "../lib/ai";
import { useThemeFonts } from "../lib/theme";

interface Props {
  current: number;
  subStep: number;
  totalCallouts: number;
}

const TOTAL = 1 + STAGES.length + 1;

function getStageId(current: number): string {
  if (current === 0) return "hero";
  if (current === TOTAL - 1) return "completion";
  return STAGES[current - 1]?.id ?? "hero";
}

export default function Sidebar({ current, subStep, totalCallouts }: Props) {
  const fonts = useThemeFonts();
  const stageId = getStageId(current);
  const stage = current > 0 && current < TOTAL - 1 ? STAGES[current - 1] : null;
  const phaseColor = stage ? PHASE_META[stage.phase].color : "var(--fg-tertiary)";
  const walkthrough = WALKTHROUGHS[stageId];
  const description = walkthrough?.description ?? stage?.description ?? "";

  const [chatHistories, setChatHistories] = useState<Record<string, AIMessage[]>>({});
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [showSetup, setShowSetup] = useState(false);
  const [provider, setProvider] = useState<Provider>("gemini");
  const [model, setModel] = useState("gemini-3-flash-preview");
  const [apiKey, setApiKey] = useState("");
  const [sidebarWidth, setSidebarWidth] = useState(340);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const dragging = useRef(false);

  const currentChat = chatHistories[stageId] ?? [];

  useEffect(() => {
    const config = getStoredConfig();
    if (config) {
      setProvider(config.provider);
      setModel(config.model);
      setApiKey(config.key);
    }
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [currentChat.length, stageId]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragging.current) return;
      const w = window.innerWidth - e.clientX;
      const clamped = Math.max(280, Math.min(w, window.innerWidth * 0.5));
      setSidebarWidth(clamped);
    };
    const onUp = () => { dragging.current = false; document.body.style.cursor = ""; document.body.style.userSelect = ""; };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); };
  }, []);

  useEffect(() => {
    document.documentElement.style.setProperty("--sidebar-width", `${sidebarWidth}px`);
  }, [sidebarWidth]);

  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, []);

  const handleSend = useCallback(async () => {
    if (!input.trim() || streaming) return;
    if (!apiKey) { setShowSetup(true); return; }

    const userMsg: AIMessage = { role: "user", content: input.trim() };
    const newHistory = [...currentChat, userMsg];
    setChatHistories((prev) => ({ ...prev, [stageId]: newHistory }));
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setStreaming(true);

    const allStagesContext = STAGES.map((s) => `## Stage ${s.number}: ${s.name}\n${s.content}`).join("\n\n");

    const walkthroughContext = walkthrough
      ? `\n\n--- Walkthrough for this stage ---\nDescription: ${walkthrough.description}\n${walkthrough.steps.map((s) => s.type === "popup" ? `Overview: ${s.text}` : `Callout: ${s.text}`).join("\n")}`
      : "";

    let systemPrompt: string;
    if (stage) {
      const stageDir = stage.githubDir ? `https://github.com/ZhangZhuoSJTU/tiny-dec/tree/main/${stage.githubDir}` : "";
      systemPrompt = `You are a teaching assistant for tiny-dec, an educational RISC-V decompiler that demonstrates the complete binary-to-C pipeline in ~18,000 lines of Python.

Project repository: https://github.com/ZhangZhuoSJTU/tiny-dec
${stageDir ? `Source code for this stage: ${stageDir}` : ""}

tiny-dec takes a compiled RISC-V ELF binary and reconstructs C source code through 19 stages: raw bytes > ELF loading > instruction decode > p-code lifting (Ghidra-style IR) > CFG construction > simplification > dataflow > SSA > call analysis > stack analysis > memory partitioning > scalar type inference > aggregate type discovery > variable recovery > range analysis > interprocedural analysis > control flow structuring > C lowering > final C output.

The user is viewing stage ${stage.number}: "${stage.name}" (${stage.description})
${totalCallouts > 0 ? `Walkthrough progress: ${subStep <= 0 ? "has not started the guided walkthrough yet" : subStep > totalCallouts ? `completed all ${totalCallouts} walkthrough steps` : `on step ${subStep} of ${totalCallouts} in the guided walkthrough`}.` : ""}

The source code is at https://github.com/ZhangZhuoSJTU/tiny-dec/tree/main/tiny_dec/ with subdirectories for each pipeline stage.

Answer concisely. Use specific addresses, register names, and p-code operations from the stage output when relevant. Explain concepts in terms of what the decompiler is doing and why. The audience may range from beginners to experienced reverse engineers. When referencing source code, include the GitHub URL.
${walkthroughContext}

--- All Stage Outputs (for cross-stage reference) ---
${allStagesContext}`;
    } else {
      systemPrompt = `You are a teaching assistant for tiny-dec, an educational RISC-V decompiler that demonstrates the complete binary-to-C decompilation pipeline in ~18,000 lines of Python.

Project repository: https://github.com/ZhangZhuoSJTU/tiny-dec
Main source: https://github.com/ZhangZhuoSJTU/tiny-dec/tree/main/tiny_dec/

tiny-dec takes a compiled RISC-V ELF binary and reconstructs C source code through 19 stages: raw bytes > ELF loading > instruction decode > p-code lifting (Ghidra-style IR) > CFG construction > simplification > dataflow > SSA > call analysis > stack analysis > memory partitioning > scalar type inference > aggregate type discovery > variable recovery > range analysis > interprocedural analysis > control flow structuring > C lowering > final C output.

The user is on the ${current === 0 ? "welcome" : "completion"} page. Answer general questions about decompilation, reverse engineering, and the tiny-dec pipeline. The source code is on GitHub if the user asks implementation questions.

--- All Stage Outputs ---
${allStagesContext}`;
    }

    let assistantText = "";
    setChatHistories((prev) => ({ ...prev, [stageId]: [...newHistory, { role: "assistant" as const, content: "" }] }));

    await streamChat(provider, model, apiKey, systemPrompt, newHistory, {
      onToken: (token) => {
        assistantText += token;
        setChatHistories((prev) => {
          const msgs = [...(prev[stageId] ?? [])];
          msgs[msgs.length - 1] = { role: "assistant", content: assistantText };
          return { ...prev, [stageId]: msgs };
        });
      },
      onDone: () => setStreaming(false),
      onError: (err) => {
        setChatHistories((prev) => {
          const msgs = [...(prev[stageId] ?? [])];
          msgs[msgs.length - 1] = { role: "assistant", content: `Error: ${err}` };
          return { ...prev, [stageId]: msgs };
        });
        setStreaming(false);
      },
    });
  }, [input, streaming, apiKey, currentChat, stageId, stage, provider, model, walkthrough, subStep, totalCallouts, current]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); e.stopPropagation(); handleSend(); }
  };

  const saveSetup = () => {
    if (apiKey.trim()) { storeConfig(provider, model, apiKey.trim()); setShowSetup(false); }
  };

  const handleClear = () => setChatHistories((prev) => ({ ...prev, [stageId]: [] }));
  const handleDisconnect = () => { clearConfig(); setApiKey(""); setShowSetup(false); };

  const models = getModels(provider);
  const inputStyle: React.CSSProperties = {
    padding: "7px 10px", borderRadius: 8, border: "1.5px solid var(--border-strong)",
    fontSize: 14, background: "var(--bg-elevated)", color: "var(--fg)",
    outline: "none", width: "100%", fontFamily: fonts.body,
  };

  return (
    <div className="sidebar" style={{ fontFamily: fonts.body }}>
      <div className="sidebar-resize-handle" onMouseDown={startResize} />
      {/* Header */}
      <div className="sidebar-header" style={{ flexDirection: "column", alignItems: "stretch", gap: 4 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0 }}>
          <div style={{ width: 3, height: 14, borderRadius: 2, background: phaseColor, flexShrink: 0 }} />
          <span style={{ fontFamily: fonts.body, fontWeight: 700, fontSize: 15, overflow: "hidden", textOverflow: "ellipsis", flex: 1 }}>
            {stage ? stage.name : current === 0 ? "Welcome" : "Complete"}
          </span>
          {stage && (
            <span className="phase-badge" style={{
              background: `${PHASE_META[stage.phase].color}15`,
              color: PHASE_META[stage.phase].color,
              border: `2px solid ${PHASE_META[stage.phase].color}30`,
              flexShrink: 0, fontWeight: 700,
            }}>
              {PHASE_META[stage.phase].label}
            </span>
          )}
          {stage?.githubDir && (
            <a href={`https://github.com/ZhangZhuoSJTU/tiny-dec/tree/main/${stage.githubDir}`}
              target="_blank" rel="noopener noreferrer"
              title="View source on GitHub"
              style={{
                display: "inline-flex", alignItems: "center", justifyContent: "center",
                width: 22, height: 22, borderRadius: 6, flexShrink: 0,
                background: "var(--bg-elevated)", border: "1.5px solid var(--border-strong)",
                boxShadow: "0 0 6px rgba(255,255,255,0.04)",
                color: "var(--fg-secondary)", transition: "color 150ms, border-color 150ms",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.color = "var(--fg)"; e.currentTarget.style.borderColor = "var(--border-focus)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = "var(--fg-secondary)"; e.currentTarget.style.borderColor = ""; }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
            </a>
          )}
        </div>
      </div>

      {/* Short functional description */}
      {description && (
        <div style={{
          padding: "10px 16px", borderBottom: "1.5px solid var(--border)",
          fontSize: 14, lineHeight: 1.55, color: "var(--fg-secondary)", fontWeight: 500,
        }}>
          {description}
        </div>
      )}

      {/* Chat messages area */}
      <div ref={scrollRef} style={{
        flex: 1, overflowY: "auto", padding: currentChat.length > 0 ? "10px 16px" : "10px 16px",
        display: "flex", flexDirection: "column", gap: 8,
      }}>
        {currentChat.length === 0 && (
          <div style={{ color: "var(--fg-tertiary)", fontSize: 13, textAlign: "center", padding: "24px 16px", fontWeight: 500 }}>
            <img src="https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/1f4ac.svg" alt="" style={{ width: 28, height: 28, marginBottom: 8, opacity: 0.5 }} /><br />
            Ask anything about this stage!
          </div>
        )}
        {currentChat.map((msg, i) => (
          <div key={`chat-${i}`} style={{
            display: "flex", justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
            gap: 6, alignItems: "flex-start",
          }}>
            {msg.role === "assistant" && (
              <img
                src="https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/1fa84.svg"
                alt="AI"
                style={{ width: 18, height: 18, flexShrink: 0, marginTop: 2 }}
              />
            )}
            <div className={msg.role === "assistant" ? "chat-markdown" : undefined} style={{
              background: msg.role === "user" ? "var(--pokeball-red)" : "var(--bg-elevated)",
              border: msg.role === "user" ? "none" : "1.5px solid var(--border)",
              borderRadius: 14,
              ...(msg.role === "user" ? { borderTopRightRadius: 4, color: "#fff" } : { borderTopLeftRadius: 4, color: "var(--fg)" }),
              padding: "6px 12px", fontSize: 14, lineHeight: 1.5,
              maxWidth: msg.role === "user" ? "85%" : "calc(100% - 28px)",
              boxShadow: "var(--shadow-sm)",
            }}>
              {msg.role === "assistant"
                ? <Markdown components={{ a: ({ children, href }) => <a href={href} target="_blank" rel="noopener noreferrer">{children}</a> }}>{msg.content || (streaming && i === currentChat.length - 1 ? "..." : "")}</Markdown>
                : (msg.content || "")}
            </div>
          </div>
        ))}
      </div>

      {/* API setup */}
      {showSetup && (
        <div style={{
          padding: 10, borderTop: "1px solid var(--border)",
          display: "flex", flexDirection: "column", gap: 6, fontSize: 14,
        }}>
          <div style={{ color: "var(--fg-tertiary)", fontSize: 12, lineHeight: 1.4 }}>
            Your key stays in your browser (localStorage). It is sent directly to the AI provider and never touches our servers.
          </div>
          <select value={provider} onChange={(e) => { setProvider(e.target.value as Provider); setModel(getModels(e.target.value as Provider)[0].id); }} style={inputStyle}>
            <option value="gemini">Gemini (recommended)</option>
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
          </select>
          {isProviderBlocked(provider) && (
            <div style={{
              padding: "6px 8px", borderRadius: 8,
              background: "rgba(232, 87, 61, 0.06)", border: "1.5px solid rgba(232, 87, 61, 0.15)",
              fontSize: 12, lineHeight: 1.4, color: "var(--accent)",
            }}>
              {isProviderBlocked(provider)}
            </div>
          )}
          <select value={model} onChange={(e) => setModel(e.target.value)} style={inputStyle}>
            {models.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
          <input type="password" placeholder="API key" value={apiKey} onChange={(e) => setApiKey(e.target.value)} style={inputStyle} />
          <div style={{ display: "flex", gap: 6 }}>
            <button onClick={saveSetup} disabled={!!isProviderBlocked(provider)} style={{
              flex: 1, padding: 6, borderRadius: 8,
              background: isProviderBlocked(provider) ? "var(--bg-hover)" : "var(--accent)",
              color: isProviderBlocked(provider) ? "var(--fg-tertiary)" : "#fff",
              border: "none", cursor: isProviderBlocked(provider) ? "not-allowed" : "pointer",
              fontSize: 14, fontWeight: 700, fontFamily: fonts.body,
            }}>Save</button>
            <button onClick={() => setShowSetup(false)} style={{
              padding: "6px 10px", borderRadius: 6, background: "var(--bg-elevated)",
              border: "1px solid var(--border-strong)", cursor: "pointer", fontSize: 14, color: "var(--fg-secondary)",
              fontFamily: fonts.body,
            }}>Cancel</button>
          </div>
          {apiKey && (
            <button onClick={handleDisconnect} style={{
              background: "none", border: "none", cursor: "pointer",
              fontSize: 12, color: "var(--fg-tertiary)", textAlign: "center",
              padding: "2px 0", textDecoration: "underline", textUnderlineOffset: 3,
            }}>Disconnect &amp; clear API key</button>
          )}
        </div>
      )}

      {/* Settings bar + Chat input */}
      <div style={{ flexShrink: 0, borderTop: "1px solid var(--border)" }}>
        {!showSetup && (
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "5px 16px", borderBottom: "1px solid var(--border)",
          }}>
            {apiKey ? (
              <span style={{ fontSize: 11, color: "var(--fg-tertiary)", fontFamily: "var(--font-mono)", letterSpacing: "0.02em" }}>
                {provider === "gemini" ? "Gemini" : provider === "anthropic" ? "Anthropic" : "OpenAI"} · {models.find(m => m.id === model)?.name ?? model}
              </span>
            ) : (
              <button onClick={() => setShowSetup(true)} style={{
                display: "inline-flex", alignItems: "center", gap: 5,
                background: "var(--accent-dim)", border: "2px solid rgba(224, 72, 50, 0.25)",
                borderRadius: 8, padding: "2px 10px", cursor: "pointer",
                color: "var(--accent)", fontSize: 11, fontWeight: 700,
              }}>
                <img src="https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/2728.svg" alt="" style={{ width: 12, height: 12 }} />
                Connect AI
              </button>
            )}
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              {apiKey && (
                <button onClick={() => setShowSetup(true)} title="AI settings" style={{
                  display: "inline-flex", alignItems: "center", gap: 4,
                  background: "none", border: "1px solid var(--border-strong)",
                  borderRadius: 4, padding: "2px 8px", cursor: "pointer",
                  color: "var(--fg-tertiary)", fontSize: 11, fontWeight: 500,
                  transition: "color 150ms, border-color 150ms",
                }}>
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>
                    <circle cx="12" cy="12" r="3"/>
                  </svg>
                  Settings
                </button>
              )}
              <button
                onClick={handleSend}
                disabled={streaming || !input.trim()}
                style={{
                  display: "inline-flex", alignItems: "center", gap: 4,
                  padding: "2px 10px", borderRadius: 8,
                  background: input.trim() ? "var(--accent)" : "transparent",
                  border: input.trim() ? "1.5px solid var(--accent)" : "1.5px solid var(--border-strong)",
                  color: input.trim() ? "#fff" : "var(--fg-tertiary)",
                  cursor: input.trim() ? "pointer" : "default",
                  fontSize: 11, fontWeight: 600,
                  transition: "all 120ms",
                }}
              >
                Send
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M5 12h14M12 5l7 7-7 7"/>
                </svg>
              </button>
            </div>
          </div>
        )}
        <div className="sidebar-input">
          <textarea
            ref={textareaRef}
            placeholder="Ask about this stage..."
            value={input}
            onChange={(e) => { setInput(e.target.value); e.target.style.height = "auto"; e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px"; }}
            onKeyDown={handleKeyDown}
            disabled={streaming}
            rows={1}
          />
        </div>
      </div>
    </div>
  );
}
