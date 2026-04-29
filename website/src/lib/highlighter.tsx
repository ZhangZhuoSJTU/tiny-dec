import type { ReactNode } from "react";

type TokenType =
  | "address"
  | "register"
  | "opcode"
  | "constant"
  | "type"
  | "comment"
  | "label"
  | "keyword"
  | "string"
  | "punct"
  | "plain";

const TOKEN_COLORS: Record<TokenType, string> = {
  address: "var(--syn-address)",
  register: "var(--syn-register)",
  opcode: "var(--syn-opcode)",
  constant: "var(--syn-constant)",
  type: "var(--syn-type)",
  comment: "var(--syn-comment)",
  label: "var(--syn-label)",
  keyword: "var(--syn-keyword)",
  string: "var(--syn-string)",
  punct: "var(--syn-punct)",
  plain: "inherit",
};

interface Token {
  type: TokenType;
  text: string;
}

export function formatEncoding(hex: string): string {
  const raw = hex.replace(/^0x/, "");
  return raw.replace(/../g, (m, i) => (i > 0 ? " " : "") + m);
}

const OPCODES = new Set([
  "INT_ADD", "INT_SUB", "INT_MULT", "INT_DIV", "INT_REM",
  "INT_LEFT", "INT_RIGHT", "INT_SRIGHT",
  "INT_AND", "INT_OR", "INT_XOR", "INT_NEGATE",
  "INT_SLESS", "INT_LESS", "INT_EQUAL", "INT_NOTEQUAL",
  "INT_SLESSEQUAL", "INT_LESSEQUAL",
  "INT_ZEXT", "INT_SEXT",
  "BOOL_NEGATE", "BOOL_AND", "BOOL_OR", "BOOL_XOR",
  "COPY", "STORE", "LOAD", "BRANCH", "CBRANCH", "CALL", "RETURN",
  "CALL_CLOBBER", "CALL_RETURN", "MEM_PHI", "PHI",
  "SUBPIECE", "INT_CARRY", "INT_SCARRY", "INT_SBORROW",
  "PIECE", "POPCOUNT",
]);

const C_KEYWORDS = new Set([
  "while", "for", "if", "else", "return", "break", "continue",
  "typedef", "struct", "union", "enum", "void",
  "static", "const", "unsigned", "signed",
  "#include", "sizeof",
]);

const C_TYPES = new Set([
  "int8_t", "int16_t", "int32_t", "int64_t",
  "uint8_t", "uint16_t", "uint32_t", "uint64_t",
  "word32_t", "bool",
]);

function tokenizeLine(line: string): Token[] {
  const tokens: Token[] = [];
  let pos = 0;

  while (pos < line.length) {
    // Comment (;-style or //-style or /* */)
    if (line[pos] === ";" || line.startsWith("//", pos)) {
      tokens.push({ type: "comment", text: line.slice(pos) });
      break;
    }
    if (line.startsWith("/*", pos)) {
      const end = line.indexOf("*/", pos + 2);
      const commentEnd = end === -1 ? line.length : end + 2;
      tokens.push({ type: "comment", text: line.slice(pos, commentEnd) });
      pos = commentEnd;
      continue;
    }

    // String literal
    if (line[pos] === '"') {
      const end = line.indexOf('"', pos + 1);
      const strEnd = end === -1 ? line.length : end + 1;
      tokens.push({ type: "string", text: line.slice(pos, strEnd) });
      pos = strEnd;
      continue;
    }

    // Hex encoding after address: "0xADDR: 0xENCODING  asm" — format encoding as spaced bytes
    const encMatch = line.slice(pos).match(/^0x([0-9a-fA-F]{8})(?=\s)/);
    if (encMatch && pos > 0 && /:\s$/.test(line.slice(0, pos))) {
      tokens.push({ type: "constant", text: formatEncoding(encMatch[0]) });
      pos += encMatch[0].length;
      continue;
    }

    // Hex address at start of line or standalone (0x followed by 4+ hex digits)
    const addrMatch = line.slice(pos).match(/^0x[0-9a-fA-F]{4,}/);
    if (addrMatch) {
      tokens.push({ type: "address", text: addrMatch[0] });
      pos += addrMatch[0].length;
      continue;
    }

    // Hex encoding (8-char hex like instruction encoding, without 0x prefix)
    const hexEncMatch = line.slice(pos).match(/^[0-9a-fA-F]{8}(?=\s)/);
    if (hexEncMatch && pos > 0 && line[pos - 1] === " ") {
      tokens.push({ type: "constant", text: formatEncoding(hexEncMatch[0]) });
      pos += hexEncMatch[0].length;
      continue;
    }

    // Register/memory references in brackets: register[0x2:4], unique[0x0:4], const[...]
    const bracketMatch = line.slice(pos).match(/^(?:register|unique|const|stack_slot|value)\[[-\w.:+x]+\]/);
    if (bracketMatch) {
      const text = bracketMatch[0];
      if (text.startsWith("register")) {
        tokens.push({ type: "register", text });
      } else if (text.startsWith("const")) {
        tokens.push({ type: "constant", text });
      } else {
        tokens.push({ type: "plain", text });
      }
      pos += text.length;
      continue;
    }

    // SSA versioned names: x10_1:4, u0_3:4
    const ssaMatch = line.slice(pos).match(/^[xum]\d+(?:_\d+)?:\d+/);
    if (ssaMatch) {
      const name = ssaMatch[0];
      if (name.startsWith("x")) {
        tokens.push({ type: "register", text: name });
      } else if (name.startsWith("m")) {
        tokens.push({ type: "constant", text: name });
      } else {
        tokens.push({ type: "plain", text: name });
      }
      pos += name.length;
      continue;
    }

    // Word boundary tokens
    const wordMatch = line.slice(pos).match(/^[a-zA-Z_#][a-zA-Z0-9_]*/);
    if (wordMatch) {
      const word = wordMatch[0];

      // Check for type names (including aggregate types like agg_8)
      const typeMatch = line.slice(pos).match(/^(?:agg_\d+\*?|int(?:8|16|32|64)_t|uint(?:8|16|32|64)_t|word32_t|bool)\b/);
      if (typeMatch) {
        tokens.push({ type: "type", text: typeMatch[0] });
        pos += typeMatch[0].length;
        // Check for trailing * (pointer)
        if (pos < line.length && line[pos] === "*") {
          tokens.push({ type: "type", text: "*" });
          pos++;
        }
        continue;
      }

      if (OPCODES.has(word)) {
        tokens.push({ type: "opcode", text: word });
        pos += word.length;
        continue;
      }

      if (C_KEYWORDS.has(word)) {
        tokens.push({ type: "keyword", text: word });
        pos += word.length;
        continue;
      }

      if (C_TYPES.has(word)) {
        tokens.push({ type: "type", text: word });
        pos += word.length;
        continue;
      }

      // Register names: x0-x31, a0-a7, s0-s11, t0-t6, sp, ra, fp, gp, tp
      const regMatch = line.slice(pos).match(/^(?:x(?:[0-9]|[12][0-9]|3[01])|[ast][0-9]|[ast]1[01]?|sp|ra|fp|gp|tp)(?=[^a-zA-Z0-9_]|$)/);
      if (regMatch) {
        tokens.push({ type: "register", text: regMatch[0] });
        pos += regMatch[0].length;
        continue;
      }

      // Labels: "block 0x...", "function 0x..."
      if ((word === "block" || word === "function" || word === "entry") && line.slice(pos + word.length).match(/^\s+0x/)) {
        tokens.push({ type: "label", text: word });
        pos += word.length;
        continue;
      }

      tokens.push({ type: "plain", text: word });
      pos += word.length;
      continue;
    }

    // Memory version: m0, m1, ...
    const memMatch = line.slice(pos).match(/^m\d+(?=[^a-zA-Z0-9_]|$)/);
    if (memMatch) {
      tokens.push({ type: "constant", text: memMatch[0] });
      pos += memMatch[0].length;
      continue;
    }

    // Numeric constants (decimal, possibly negative)
    const numMatch = line.slice(pos).match(/^-?\d+(?=[^a-zA-Z0-9_]|$)/);
    if (numMatch) {
      tokens.push({ type: "constant", text: numMatch[0] });
      pos += numMatch[0].length;
      continue;
    }

    // Arrow operators
    if (line.startsWith("<-", pos) || line.startsWith("->", pos)) {
      tokens.push({ type: "punct", text: line.slice(pos, pos + 2) });
      pos += 2;
      continue;
    }

    // Comparison operators
    if (line.startsWith("<s", pos) && (pos + 2 >= line.length || !line[pos + 2].match(/[a-zA-Z0-9_]/))) {
      tokens.push({ type: "opcode", text: "<s" });
      pos += 2;
      continue;
    }

    // Punctuation
    if ("(){}[]<>=!&|+*/%^~,;:.@#".includes(line[pos])) {
      tokens.push({ type: "punct", text: line[pos] });
      pos++;
      continue;
    }

    // Whitespace
    const wsMatch = line.slice(pos).match(/^\s+/);
    if (wsMatch) {
      tokens.push({ type: "plain", text: wsMatch[0] });
      pos += wsMatch[0].length;
      continue;
    }

    // Fallback: single character
    tokens.push({ type: "plain", text: line[pos] });
    pos++;
  }

  return tokens;
}

export function highlightLine(line: string): ReactNode[] {
  return tokenizeLine(line).map((token, i) => (
    <span key={i} style={token.type !== "plain" ? { color: TOKEN_COLORS[token.type] } : undefined}>
      {token.text}
    </span>
  ));
}

export function highlightCode(code: string, cascade?: boolean): ReactNode {
  const lines = code.split("\n");
  return lines.map((line, i) => (
    <span
      key={i}
      style={cascade ? { animationDelay: `${i * 8}ms` } : undefined}
    >
      {highlightLine(line)}
      {i < lines.length - 1 ? "\n" : ""}
    </span>
  ));
}
