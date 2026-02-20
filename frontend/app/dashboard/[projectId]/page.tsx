"use client";

import { useEffect, useState } from 'react';
import axios from 'axios';
import { useParams } from 'next/navigation';
import ServiceGraph from '@/components/ServiceGraph';
import CodeViewer from '@/components/CodeViewer';
import { transformToReactFlow } from '@/lib/graphTransformer';
import { Node } from '@xyflow/react';
import { Loader2 } from 'lucide-react';

export default function DashboardPage() {
  const params = useParams();
  const projectId = params.projectId as string;

  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedFile, setSelectedFile] = useState<{code: string, lang: string} | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      if (!projectId) return;
      try {
        // Fetch Project Context from Backend
        // NOTE: Ensure your backend has CORS enabled!
        const response = await axios.get(`http://localhost:8000/analyze/${projectId}`); // Or a generic GET endpoint if you have one
        // If you don't have a direct GET /analyze/{id}, use the stored data logic or /ingest endpoints
        
        // For now, assuming GET /analyze/{projectId} returns the ProjectContext JSON
        // If that endpoint doesn't exist yet, we might need to mock it or use the data you just generated.
        
        // MOCK DATA FALLBACK (If API fails during dev)
        // Remove this in production
        /* const mockData = { nodes: [...], edges: [...] }; 
        const { nodes: layoutedNodes, edges: layoutedEdges } = transformToReactFlow(mockData);
        */

        const { nodes: layoutedNodes, edges: layoutedEdges } = transformToReactFlow(response.data);
        
        setNodes(layoutedNodes);
        setEdges(layoutedEdges);
      } catch (error) {
        console.error("Failed to fetch project data:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [projectId]);

  const handleNodeClick = (node: Node) => {
    // When a node is clicked, show its content in the editor
    if (node.data && node.data.code) {
      setSelectedFile({
        code: node.data.code as string,
        lang: node.data.language as string || 'plaintext'
      });
    } else {
        setSelectedFile({
            code: "// No content available for this node",
            lang: "plaintext"
        });
    }
  };

  if (loading) {
    return (
        <div className="h-screen w-full flex items-center justify-center">
            <Loader2 className="animate-spin w-10 h-10 text-blue-500" />
            <span className="ml-2 text-lg text-gray-600">Loading Project Context...</span>
        </div>
    );
  }

  return (
    <div className="flex h-screen w-full overflow-hidden">
      {/* LEFT PANE: Graph Visualization (60%) */}
      <div className="w-3/5 h-full relative border-r border-gray-300">
        <ServiceGraph 
            initialNodes={nodes} 
            initialEdges={edges} 
            onNodeClick={handleNodeClick} 
        />
      </div>

      {/* RIGHT PANE: Code Editor (40%) */}
      <div className="w-2/5 h-full bg-[#1e1e1e]">
        {selectedFile ? (
            <CodeViewer 
                code={selectedFile.code} 
                language={selectedFile.lang} 
            />
        ) : (
            <div className="h-full flex items-center justify-center text-gray-500">
                <p>Select a node to view code</p>
            </div>
        )}
      </div>
    </div>
  );
}