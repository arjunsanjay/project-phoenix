"use client";

import React, { useCallback } from 'react';
import { 
    ReactFlow, 
    Controls, 
    Background, 
    useNodesState, 
    useEdgesState,
    Node 
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

interface ServiceGraphProps {
  initialNodes: Node[];
  initialEdges: any[];
  onNodeClick: (node: Node) => void;
}

export default function ServiceGraph({ initialNodes, initialEdges, onNodeClick }: ServiceGraphProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const handleNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
    onNodeClick(node);
  }, [onNodeClick]);

  return (
    <div className="h-full w-full bg-slate-50">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        fitView
      >
        <Background gap={12} size={1} />
        <Controls />
      </ReactFlow>
      
      <div className="absolute top-4 left-4 bg-white p-2 rounded shadow text-sm z-10">
        <p className="font-bold">Graph Legend</p>
        <div className="flex items-center gap-2 mt-1">
          <span className="w-3 h-3 bg-white border border-gray-500 rounded-sm block"></span>
          <span>Source File</span>
        </div>
      </div>
    </div>
  );
}