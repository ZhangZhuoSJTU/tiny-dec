import dagre from "@dagrejs/dagre";
import type { CFGBlock, CFGEdge } from "../data/stages";

export interface PositionedNode {
  address: string;
  label?: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface PositionedEdge {
  source: string;
  target: string;
  label?: string;
  type: "normal" | "back";
  points: { x: number; y: number }[];
}

export interface GraphLayout {
  nodes: PositionedNode[];
  edges: PositionedEdge[];
  width: number;
  height: number;
}

export function computeLayout(
  blocks: CFGBlock[],
  edges: CFGEdge[],
  nodeWidths: Map<string, number>,
  nodeHeights: Map<string, number>,
): GraphLayout {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "TB", nodesep: 80, ranksep: 100, marginx: 30, marginy: 30 });
  g.setDefaultEdgeLabel(() => ({}));

  for (const block of blocks) {
    const w = nodeWidths.get(block.address) ?? 220;
    const h = nodeHeights.get(block.address) ?? 80;
    g.setNode(block.address, { width: w, height: h, label: block.label });
  }

  for (const edge of edges) {
    g.setEdge(edge.source, edge.target, { label: edge.label });
  }

  dagre.layout(g);

  const posNodes: PositionedNode[] = blocks.map((block) => {
    const node = g.node(block.address);
    return {
      address: block.address,
      label: block.label,
      x: node.x - node.width / 2,
      y: node.y - node.height / 2,
      width: node.width,
      height: node.height,
    };
  });

  const posEdges: PositionedEdge[] = edges.map((edge) => {
    const dagreEdge = g.edge(edge.source, edge.target);
    return {
      source: edge.source,
      target: edge.target,
      label: edge.label,
      type: edge.type,
      points: dagreEdge.points ?? [],
    };
  });

  const graphInfo = g.graph();
  return {
    nodes: posNodes,
    edges: posEdges,
    width: (graphInfo.width ?? 600) + 40,
    height: (graphInfo.height ?? 400) + 40,
  };
}
