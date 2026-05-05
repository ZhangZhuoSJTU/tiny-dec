export type DiffLineType = "unchanged" | "added" | "removed" | "modified";

export interface DiffLine {
  type: DiffLineType;
  text: string;
  oldText?: string;
}

export interface BlockDiff {
  address: string;
  lines: DiffLine[];
}

export function diffBlockIR(oldIR: string, newIR: string): DiffLine[] {
  const oldLines = oldIR.split("\n").filter((l) => l.trim() !== "");
  const newLines = newIR.split("\n").filter((l) => l.trim() !== "");

  const result: DiffLine[] = [];
  const oldSet = new Set(oldLines);
  const newSet = new Set(newLines);

  let oi = 0;
  let ni = 0;

  while (oi < oldLines.length || ni < newLines.length) {
    if (oi < oldLines.length && ni < newLines.length) {
      if (oldLines[oi] === newLines[ni]) {
        result.push({ type: "unchanged", text: newLines[ni] });
        oi++;
        ni++;
      } else if (!newSet.has(oldLines[oi]) && !oldSet.has(newLines[ni])) {
        result.push({ type: "modified", text: newLines[ni], oldText: oldLines[oi] });
        oi++;
        ni++;
      } else if (!newSet.has(oldLines[oi])) {
        result.push({ type: "removed", text: oldLines[oi] });
        oi++;
      } else {
        result.push({ type: "added", text: newLines[ni] });
        ni++;
      }
    } else if (oi < oldLines.length) {
      result.push({ type: "removed", text: oldLines[oi] });
      oi++;
    } else {
      result.push({ type: "added", text: newLines[ni] });
      ni++;
    }
  }

  return result;
}

export function diffCFG(
  oldBlocks: { address: string; ir: string }[],
  newBlocks: { address: string; ir: string }[],
): BlockDiff[] {
  const oldMap = new Map(oldBlocks.map((b) => [b.address, b.ir]));
  const newMap = new Map(newBlocks.map((b) => [b.address, b.ir]));
  const allAddresses = new Set([...oldMap.keys(), ...newMap.keys()]);
  const result: BlockDiff[] = [];

  for (const addr of allAddresses) {
    const oldIR = oldMap.get(addr);
    const newIR = newMap.get(addr);

    if (oldIR && newIR) {
      result.push({ address: addr, lines: diffBlockIR(oldIR, newIR) });
    } else if (newIR) {
      result.push({
        address: addr,
        lines: newIR.split("\n").filter((l) => l.trim()).map((l) => ({ type: "added" as const, text: l })),
      });
    } else if (oldIR) {
      result.push({
        address: addr,
        lines: oldIR.split("\n").filter((l) => l.trim()).map((l) => ({ type: "removed" as const, text: l })),
      });
    }
  }

  return result;
}
