export type Provider = "openai" | "gemini" | "anthropic";

export interface AIMessage {
  role: "user" | "assistant";
  content: string;
}

interface StreamCallbacks {
  onToken: (token: string) => void;
  onDone: () => void;
  onError: (error: string) => void;
}

const OPENAI_MODELS = [
  { id: "gpt-4.1-mini", name: "GPT-4.1 Mini" },
];

const GEMINI_MODELS = [
  { id: "gemini-3-flash-preview", name: "Gemini 3 Flash" },
  { id: "gemini-3.1-pro-preview", name: "Gemini 3.1 Pro" },
  { id: "gemini-2.5-flash", name: "Gemini 2.5 Flash" },
];

const ANTHROPIC_MODELS = [
  { id: "claude-opus-4-7", name: "Claude Opus 4.7" },
  { id: "claude-sonnet-4-6", name: "Claude Sonnet 4.6" },
  { id: "claude-haiku-4-5-20251001", name: "Claude Haiku 4.5" },
];

export function getModels(provider: Provider) {
  if (provider === "openai") return OPENAI_MODELS;
  if (provider === "anthropic") return ANTHROPIC_MODELS;
  return GEMINI_MODELS;
}

export function isProviderBlocked(provider: Provider): string | null {
  if (provider === "openai") return "OpenAI does not allow browser-side API calls (CORS). Use Gemini or Anthropic instead.";
  return null;
}

export function getStoredConfig(): { provider: Provider; model: string; key: string } | null {
  try {
    const raw = localStorage.getItem("tiny-dec-ai");
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function storeConfig(provider: Provider, model: string, key: string) {
  localStorage.setItem("tiny-dec-ai", JSON.stringify({ provider, model, key }));
}

export function clearConfig() {
  localStorage.removeItem("tiny-dec-ai");
}

export async function streamChat(
  provider: Provider,
  model: string,
  apiKey: string,
  systemPrompt: string,
  messages: AIMessage[],
  callbacks: StreamCallbacks,
) {
  try {
    if (provider === "openai") {
      await streamOpenAI(model, apiKey, systemPrompt, messages, callbacks);
    } else if (provider === "anthropic") {
      await streamAnthropic(model, apiKey, systemPrompt, messages, callbacks);
    } else {
      await streamGemini(model, apiKey, systemPrompt, messages, callbacks);
    }
  } catch (e) {
    callbacks.onError(e instanceof Error ? e.message : "Unknown error");
  }
}

async function streamOpenAI(
  model: string,
  apiKey: string,
  systemPrompt: string,
  messages: AIMessage[],
  { onToken, onDone, onError }: StreamCallbacks,
) {
  const res = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model,
      stream: true,
      messages: [
        { role: "system", content: systemPrompt },
        ...messages.map((m) => ({ role: m.role, content: m.content })),
      ],
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    onError(`OpenAI API error (${res.status}): ${err}`);
    return;
  }

  const reader = res.body?.getReader();
  if (!reader) { onError("No response body"); return; }
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const data = line.slice(6).trim();
      if (data === "[DONE]") { onDone(); return; }
      try {
        const parsed = JSON.parse(data);
        const token = parsed.choices?.[0]?.delta?.content;
        if (token) onToken(token);
      } catch { /* skip malformed chunks */ }
    }
  }
  onDone();
}

async function streamGemini(
  model: string,
  apiKey: string,
  systemPrompt: string,
  messages: AIMessage[],
  { onToken, onDone, onError }: StreamCallbacks,
) {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:streamGenerateContent?alt=sse&key=${apiKey}`;
  const contents = messages.map((m) => ({
    role: m.role === "assistant" ? "model" : "user",
    parts: [{ text: m.content }],
  }));

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      system_instruction: { parts: [{ text: systemPrompt }] },
      contents,
      tools: [{ google_search: {} }],
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    onError(`Gemini API error (${res.status}): ${err}`);
    return;
  }

  const reader = res.body?.getReader();
  if (!reader) { onError("No response body"); return; }
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const data = line.slice(6).trim();
      try {
        const parsed = JSON.parse(data);
        const text = parsed.candidates?.[0]?.content?.parts?.[0]?.text;
        if (text) onToken(text);
      } catch { /* skip */ }
    }
  }
  onDone();
}

async function streamAnthropic(
  model: string,
  apiKey: string,
  systemPrompt: string,
  messages: AIMessage[],
  { onToken, onDone, onError }: StreamCallbacks,
) {
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
      "anthropic-dangerous-direct-browser-access": "true",
    },
    body: JSON.stringify({
      model,
      max_tokens: 4096,
      stream: true,
      system: systemPrompt,
      messages: messages.map((m) => ({ role: m.role, content: m.content })),
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    onError(`Anthropic API error (${res.status}): ${err}`);
    return;
  }

  const reader = res.body?.getReader();
  if (!reader) { onError("No response body"); return; }
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const data = line.slice(6).trim();
      try {
        const parsed = JSON.parse(data);
        if (parsed.type === "content_block_delta" && parsed.delta?.text) {
          onToken(parsed.delta.text);
        }
      } catch { /* skip */ }
    }
  }
  onDone();
}
