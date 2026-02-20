"use client";

import Editor from "@monaco-editor/react";

interface CodeViewerProps {
  code: string;
  language: string;
  readOnly?: boolean;
}

export default function CodeViewer({ code, language, readOnly = true }: CodeViewerProps) {
  // Simple language mapping for Monaco
  const getLanguage = (lang: string) => {
    if (!lang) return "plaintext";
    const map: Record<string, string> = {
      python: "python",
      javascript: "javascript",
      typescript: "typescript",
      c_sharp: "csharp",
      go: "go",
      java: "java",
      json: "json",
      dockerfile: "dockerfile",
      hcl: "hcl",
      yaml: "yaml"
    };
    return map[lang.toLowerCase()] || "plaintext";
  };

  return (
    <div className="h-full w-full border-l border-gray-200">
      <div className="bg-gray-100 p-2 border-b border-gray-300 font-mono text-sm font-semibold flex justify-between items-center">
        <span>File Viewer</span>
        <span className="text-xs text-gray-500 uppercase">{language}</span>
      </div>
      <Editor
        height="90vh"
        language={getLanguage(language)}
        value={code}
        theme="vs-dark"
        options={{
          readOnly: readOnly,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          fontSize: 14,
        }}
      />
    </div>
  );
}