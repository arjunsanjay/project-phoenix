import dagre from 'dagre';
import { Node, Edge, Position } from '@xyflow/react';

const nodeWidth = 220;
const nodeHeight = 50;

export const transformToReactFlow = (apiData: any) => {
  if (!apiData || !apiData.nodes) return { nodes: [], edges: [] };

  // 1. Map API Nodes to React Flow Nodes
  const initialNodes: Node[] = apiData.nodes.map((node: any) => ({
    id: node.id,
    type: 'default', 
    data: { 
        label: node.id.split('/').pop(), 
        fullPath: node.id,
        language: node.language,
        code: node.content,
        nodeType: node.type // <--- Pass the type to data
    },
    position: { x: 0, y: 0 },
    style: { 
        border: node.type === 'SERVICE' ? '2px solid #2563eb' : '1px solid #777', // Blue border for Services
        padding: '10px', 
        borderRadius: '5px',
        // Blue background for Service nodes, White for files
        background: node.type === 'SERVICE' ? '#eff6ff' : '#ffffff', 
        color: '#000000',
        fontSize: '12px',
        fontWeight: node.type === 'SERVICE' ? '700' : '500', // Bold text for Services
        width: 220,
        textAlign: 'center',
    },
  }));

  // 2. Map API Edges to React Flow Edges
  const initialEdges: Edge[] = apiData.edges.map((edge: any, index: number) => ({
    id: `e-${edge.source}-${edge.target}`,
    source: edge.source,
    target: edge.target,
    animated: true,
    style: { stroke: '#b1b1b7', strokeWidth: 2 },
    type: 'smoothstep' // Better for architecture diagrams
  }));

  return getLayoutedElements(initialNodes, initialEdges);
};

// Layout logic (Dagre)
export const getLayoutedElements = (nodes: Node[], edges: Edge[]) => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  // Rankdir 'LR' = Left to Right. 'TB' = Top to Bottom.
  dagreGraph.setGraph({ rankdir: 'LR' });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      targetPosition: Position.Left,
      sourcePosition: Position.Right,
      position: {
        x: nodeWithPosition.x - nodeWidth / 2,
        y: nodeWithPosition.y - nodeHeight / 2,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
};