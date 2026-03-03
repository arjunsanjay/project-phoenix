import dagre from 'dagre';
import { Node, Edge, Position } from '@xyflow/react';
import { DecompositionProposal } from './types';

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

export const transformDecompositionToReactFlow = (proposal: any) => {
    if (!proposal || !proposal.proposed_services) return { nodes: [], edges: [] };
  
    // 1. Map Proposed Services to Nodes
    const initialNodes: Node[] = proposal.proposed_services.map((svc: any) => ({
      id: svc.service_name,
      type: 'default',
      data: {
        label: svc.service_name,
        ...svc, // Inject all the DDD data (bounded_context, endpoints, etc.)
        isDecompositionNode: true // Flag to help the UI know what panel to show
      },
      position: { x: 0, y: 0 },
      style: {
        border: '2px solid #8b5cf6', // Distinctive Purple border for proposed architecture
        padding: '12px',
        borderRadius: '8px',
        background: '#f5f3ff', // Light purple background
        color: '#4c1d95',
        fontSize: '13px',
        fontWeight: '700',
        width: 220,
        textAlign: 'center',
      },
    }));
  
    // 2. Map Integration Points to Edges
    const initialEdges: Edge[] = proposal.integration_points.map((pt: any, idx: number) => ({
      id: `e-decomp-${pt.source_service}-${pt.target_service}-${idx}`,
      source: pt.source_service,
      target: pt.target_service,
      animated: true,
      label: pt.communication_pattern, // e.g., "Synchronous (REST)"
      labelStyle: { fill: '#6b7280', fontWeight: 500, fontSize: 10 },
      labelBgStyle: { fill: '#ffffff', fillOpacity: 0.8 },
      style: { stroke: '#8b5cf6', strokeWidth: 2 },
      type: 'smoothstep'
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