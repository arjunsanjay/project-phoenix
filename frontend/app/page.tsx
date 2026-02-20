'use client';

import React, { useState, useCallback } from 'react';
import { 
  ReactFlow, 
  Background, 
  Controls, 
  useNodesState, 
  useEdgesState, 
  Node, 
  Edge 
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import Editor from '@monaco-editor/react';
import { 
  Download, Layers, Box, Terminal, Play, 
  Database, ShieldCheck, Activity, CheckCircle, Cloud, FileCode 
} from 'lucide-react';
import { transformToReactFlow } from '@/lib/graphTransformer';

// --- TYPES ---
type AppNodeData = {
  label: string;
  code?: string;
  language?: string;
  nodeType?: string;
  [key: string]: any;
};

type Resource = {
  resource_type: string;
  engine: string;
  reason: string;
  approved: boolean;
  terraform_module: string;
  suggested_tier: string; // Fixed: Added missing field
};

type Proposal = {
  project_id: string;
  cloud_provider: string;
  terraform_config: { region: string; vpc_cidr: string };
  detected_resources: Resource[];
};

export default function Dashboard() {
  // --- STATE ---
  const [projectId, setProjectId] = useState<string | null>(null);
  const [view, setView] = useState<'graph' | 'infra'>('graph');
  
  // Graph Data
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  
  // GLOBAL FILE MEMORY (Prevents data loss when switching nodes)
  // Format: { "node_id": { "docker": "...", "k8s": "..." } }
  const [fileStore, setFileStore] = useState<Record<string, { docker?: string; k8s?: string }>>({});

  // Right Panel UI State
  const [activeTab, setActiveTab] = useState<'code' | 'docker' | 'k8s'>('code');
  const [editorContent, setEditorContent] = useState<string>("// Select a service...");
  const [isGenerating, setIsGenerating] = useState(false);

  // Infra State (Multi-File Support)
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [terraformFiles, setTerraformFiles] = useState<Record<string, string>>({});
  const [activeTerraformFile, setActiveTerraformFile] = useState<string>("main.tf");

  // --- HANDLERS ---

  const onNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
    setSelectedNode(node);
    setActiveTab('code'); // Default to source code view
    
    // Check memory: Do we already have files for this node?
    const storedFiles = fileStore[node.id];
    
    // Update editor content based on what we have in memory
    setEditorContent(node.data.code as string || "// No source code available");
  }, [fileStore]);

  // Handle Tab Switching with Memory Check
  const handleTabSwitch = (tab: 'code' | 'docker' | 'k8s') => {
    setActiveTab(tab);
    if (!selectedNode) return;

    if (tab === 'code') {
        setEditorContent(selectedNode.data.code as string || "// No code");
    } else if (tab === 'docker') {
        const stored = fileStore[selectedNode.id]?.docker;
        setEditorContent(stored || "// Click Generate to build Dockerfile...");
    } else if (tab === 'k8s') {
        const stored = fileStore[selectedNode.id]?.k8s;
        setEditorContent(stored || "// Click Generate to build K8s Manifests...");
    }
  };

  const handleAnalyze = async (url: string) => {
    setIsGenerating(true);
    const formData = new FormData();
    formData.append('url', url);
    try {
      const res = await fetch('http://localhost:8000/analyze/git', { method: 'POST', body: formData });
      if (!res.ok) throw new Error("Backend failed");
      
      const data = await res.json();
      setProjectId(data.project_id);
      const { nodes: flowNodes, edges: flowEdges } = transformToReactFlow(data);
      setNodes(flowNodes);
      setEdges(flowEdges);
      setView('graph');
    } catch (err) { 
      alert("Analysis Failed. Check console."); 
      console.error(err);
    } 
    finally { setIsGenerating(false); }
  };

  // --- GENERATORS (With Streaming) ---

  const generateDocker = async () => {
    if (!projectId || !selectedNode) return;
    
    setIsGenerating(true);
    setEditorContent(""); // Clear for streaming effect
    let accumulatedCode = "";

    try {
      const res = await fetch('http://localhost:8000/generate/docker', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: projectId, node_id: selectedNode.id })
      });

      if (!res.body) throw new Error("No response body");

      // STREAM READER LOOP
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let done = false;

      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        if (value) {
          const chunk = decoder.decode(value);
          accumulatedCode += chunk;
          setEditorContent(accumulatedCode); // Real-time update
        }
      }
      
      // Save to Memory Store
      setFileStore(prev => ({
        ...prev,
        [selectedNode.id]: { ...prev[selectedNode.id], docker: accumulatedCode }
      }));
      
    } catch (err) { 
        setEditorContent(`// Error: ${err}`); 
    } 
    finally { setIsGenerating(false); }
  };

  const generateK8s = async () => {
    if (!projectId || !selectedNode) return;
    setIsGenerating(true);
    setEditorContent("// Generating Kubernetes Manifests...");

    try {
      const payload = {
        project_id: projectId,
        service_name: selectedNode.data.label,
        image_name: `${selectedNode.data.label}:latest`, 
        container_port: 8080,
        replicas: 2,
        env_vars: []
      };

      const res = await fetch('http://localhost:8000/generate/k8s', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      
      const combinedYaml = `# ConfigMap\n${data.configmap_yaml}\n\n---\n# Deployment\n${data.deployment_yaml}\n\n---\n# Service\n${data.service_yaml}`;
      
      // Save to Memory Store
      setFileStore(prev => ({
        ...prev,
        [selectedNode.id]: { ...prev[selectedNode.id], k8s: combinedYaml }
      }));
      setEditorContent(combinedYaml);

    } catch (err) { setEditorContent(`// Error: ${err}`); } 
    finally { setIsGenerating(false); }
  };

  // --- INFRASTRUCTURE HANDLERS ---

  const fetchProposal = async () => {
    if (!projectId) return alert("Please analyze a project first");
    setIsGenerating(true);
    try {
      const res = await fetch(`http://localhost:8000/infra/proposal/${projectId}`);
      const data = await res.json();
      setProposal(data);
      setView('infra');
    } catch (err) { console.error(err); } 
    finally { setIsGenerating(false); }
  };

  const toggleResource = (index: number) => {
    if (!proposal) return;
    
    // Deep copy for robust state update
    const updated = { ...proposal };
    const resources = [...updated.detected_resources];
    
    resources[index] = {
        ...resources[index],
        approved: !resources[index].approved
    };
    
    updated.detected_resources = resources;
    setProposal(updated);
  };

  const generateTerraform = async () => {
    if (!proposal) return;
    setIsGenerating(true);
    setTerraformFiles({ "main.tf": "// Architecting Infrastructure... please wait..." });
    setActiveTerraformFile("main.tf");
    
    try {
      const res = await fetch('http://localhost:8000/infra/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(proposal)
      });
      const data = await res.json();
      setTerraformFiles(data.terraform_files); // Expecting dict of files now
      setActiveTerraformFile("main.tf");
    } catch (err) { console.error(err); } 
    finally { setIsGenerating(false); }
  };

  // --- RENDER HELPERS ---
  const isServiceNode = selectedNode?.data?.nodeType === 'SERVICE';

  return (
    <div className="flex h-screen bg-gray-50 text-gray-900 font-sans">
      
      {/* 1. SIDEBAR */}
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col justify-between z-20">
        <div className="p-6">
          <div className="flex items-center gap-2 mb-8">
            <Layers className="w-8 h-8 text-blue-600" />
            <h1 className="text-xl font-bold tracking-tight">Phoenix</h1>
          </div>
          <nav className="space-y-2">
            <button onClick={() => setView('graph')} className={`flex items-center gap-3 w-full px-3 py-2 rounded-md font-medium transition-colors ${view === 'graph' ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-100'}`}>
              <Activity className="w-4 h-4" /> Dashboard
            </button>
            <button onClick={fetchProposal} className={`flex items-center gap-3 w-full px-3 py-2 rounded-md font-medium transition-colors ${view === 'infra' ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-100'}`}>
              <Database className="w-4 h-4" /> Infrastructure
            </button>
          </nav>
        </div>
        <div className="p-6 border-t border-gray-200">
          <div className="mb-4">
            <label className="block text-xs font-semibold text-gray-500 uppercase mb-2">Analyze Repo</label>
            <input type="text" placeholder="https://github.com/..." className="w-full text-sm border border-gray-300 rounded px-3 py-2 outline-none" onKeyDown={(e) => e.key === 'Enter' && handleAnalyze(e.currentTarget.value)} />
          </div>
          <button className="flex items-center justify-center gap-2 w-full bg-black text-white py-2 rounded-md text-sm hover:bg-gray-800 transition shadow-sm">
            <Download className="w-4 h-4" /> Export Project
          </button>
        </div>
      </aside>

      {/* 2. MAIN CONTENT AREA */}
      <main className="flex-1 flex flex-col relative h-full overflow-hidden">
        
        {/* GRAPH VIEW */}
        {view === 'graph' && (
          <div className="flex-1 w-full h-full bg-gray-50 relative">
             <div className="absolute top-4 left-4 z-10 bg-white/90 backdrop-blur px-4 py-2 rounded-lg shadow-sm border border-gray-200">
               <h2 className="text-sm font-semibold text-gray-700">Service Map</h2>
             </div>
             <ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onNodeClick={onNodeClick} fitView minZoom={0.1}>
               <Background color="#e5e7eb" gap={20} />
               <Controls className="bg-white border-gray-200 shadow-sm" />
             </ReactFlow>
          </div>
        )}

        {/* INFRASTRUCTURE VIEW */}
        {view === 'infra' && (
          <div className="flex-1 flex flex-col p-8 overflow-y-auto bg-gray-50">
            <div className="max-w-6xl mx-auto w-full grid grid-cols-12 gap-6 h-[80vh]">
                
                {/* LEFT: CHECKLIST (Col 4) */}
                <div className="col-span-4 bg-white p-6 rounded-xl shadow-sm border border-gray-200 flex flex-col h-full">
                    <h3 className="font-semibold text-lg mb-4 flex items-center gap-2">
                        <CheckCircle className="w-5 h-5 text-green-500" /> Resources
                    </h3>
                    
                    {!proposal ? (
                        <div className="flex-1 flex items-center justify-center text-gray-400 text-sm italic">
                            No project loaded.
                        </div>
                    ) : (
                        <div className="flex-1 overflow-y-auto space-y-3">
                            {proposal.detected_resources.map((res, idx) => (
                                <div 
                                    key={idx} 
                                    onClick={() => toggleResource(idx)} 
                                    className={`p-4 rounded-lg border cursor-pointer transition-all duration-200 relative overflow-hidden ${
                                        res.approved 
                                        ? 'border-blue-600 bg-blue-50 shadow-sm ring-1 ring-blue-600' 
                                        : 'border-gray-200 hover:border-blue-300 hover:bg-gray-50'
                                    }`}
                                >
                                    {res.approved && (
                                        <div className="absolute top-0 right-0 bg-blue-600 text-white text-[10px] px-2 py-0.5 rounded-bl-lg font-bold">
                                            APPROVED
                                        </div>
                                    )}
                                    <div className="flex items-center gap-3">
                                        <div className={`w-5 h-5 rounded-md border flex items-center justify-center transition-colors ${res.approved ? 'bg-blue-600 border-blue-600' : 'border-gray-400'}`}>
                                            {res.approved && <CheckCircle className="w-3.5 h-3.5 text-white" />}
                                        </div>
                                        <div>
                                            <h4 className={`font-medium capitalize ${res.approved ? 'text-blue-900' : 'text-gray-700'}`}>{res.resource_type}</h4>
                                            <p className="text-xs text-gray-500">{res.engine} • {res.suggested_tier}</p>
                                        </div>
                                    </div>
                                    <p className="text-xs text-gray-500 mt-3 pl-8 italic border-l-2 border-gray-200">
                                       "{res.reason}"
                                    </p>
                                </div>
                            ))}
                        </div>
                    )}

                    <button onClick={generateTerraform} disabled={isGenerating || !proposal} className="mt-6 w-full bg-black text-white py-3 rounded-lg font-medium hover:bg-gray-800 disabled:opacity-50 flex justify-center items-center gap-2">
                        {isGenerating ? 'Architecting...' : <><Play className="w-4 h-4" /> Generate Terraform</>}
                    </button>
                </div>

                {/* RIGHT: OUTPUT TABS (Col 8) */}
                <div className="col-span-8 bg-gray-900 rounded-xl shadow-lg border border-gray-800 overflow-hidden flex flex-col h-full">
                    {/* File Tabs */}
                    <div className="bg-gray-800 px-2 flex overflow-x-auto border-b border-gray-700">
                        {Object.keys(terraformFiles).length > 0 ? Object.keys(terraformFiles).map(fileName => (
                            <button
                                key={fileName}
                                onClick={() => setActiveTerraformFile(fileName)}
                                className={`px-4 py-3 text-xs font-mono border-r border-gray-700 hover:bg-gray-700 transition-colors ${activeTerraformFile === fileName ? 'bg-gray-900 text-blue-400 border-b-2 border-b-blue-400' : 'text-gray-400'}`}
                            >
                                <div className="flex items-center gap-2">
                                    <FileCode className="w-3 h-3" /> {fileName}
                                </div>
                            </button>
                        )) : (
                            <div className="px-4 py-3 text-xs font-mono text-gray-500">Waiting for generation...</div>
                        )}
                    </div>
                    
                    {/* Editor */}
                    <div className="flex-1">
                        <Editor
                            height="100%"
                            defaultLanguage="hcl"
                            theme="vs-dark"
                            value={terraformFiles[activeTerraformFile] || ""}
                            options={{ minimap: { enabled: false }, fontSize: 13, readOnly: true, automaticLayout: true }}
                        />
                    </div>
                </div>
            </div>
          </div>
        )}
      </main>

      {/* 3. RIGHT INSPECTOR (Visible only in Graph View) */}
      {view === 'graph' && (
        <aside className="w-[500px] bg-white border-l border-gray-200 flex flex-col shadow-xl z-30">
            {/* Header with Tabs */}
            <div className="h-14 border-b border-gray-200 flex items-center px-4 justify-between bg-gray-50">
            <span 
  className="font-semibold text-sm truncate max-w-[200px]" 
  title={selectedNode ? (selectedNode.data.label as string) : ''}
>
                    {selectedNode ? selectedNode.data.label as string : 'Select a Service'}
                </span>
                <div className="flex gap-1 bg-gray-200 p-1 rounded-lg">
                    {['code', 'docker', 'k8s'].map((tab) => (
                        <button 
                            key={tab}
                            onClick={() => handleTabSwitch(tab as any)}
                            className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${activeTab === tab ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
                        >
                            {tab.charAt(0).toUpperCase() + tab.slice(1)}
                        </button>
                    ))}
                </div>
            </div>

            {/* Action Bar */}
            {activeTab !== 'code' && (
                <div className="p-4 bg-gray-50 border-b flex justify-between items-center">
                    <h3 className="text-xs font-bold uppercase text-gray-500">
                        {isServiceNode ? `AI ${activeTab === 'docker' ? 'Docker' : 'K8s'} Architect` : 'Select a Service Node'}
                    </h3>
                    <button 
                        onClick={activeTab === 'docker' ? generateDocker : generateK8s}
                        disabled={!isServiceNode || isGenerating}
                        className="flex items-center gap-1 bg-blue-600 text-white text-xs px-3 py-1.5 rounded hover:bg-blue-700 disabled:opacity-50"
                    >
                        {isGenerating ? 'Generating...' : <><Play className="w-3 h-3" /> Generate</>}
                    </button>
                </div>
            )}

            <div className="flex-1 overflow-hidden relative">
                <Editor
                    height="100%"
                    defaultLanguage={activeTab === 'code' ? 'java' : activeTab === 'docker' ? 'dockerfile' : 'yaml'}
                    value={editorContent}
                    options={{ minimap: { enabled: false }, fontSize: 12, readOnly: true, automaticLayout: true }}
                />
            </div>
        </aside>
      )}
    </div>
  );
}