'use client';

import { ChatMessage } from '@/lib/types';

interface ToolCallDisplayProps {
  toolCallMessage: ChatMessage;
  toolResultMessage?: ChatMessage;
}

export default function ToolCallDisplay({ toolCallMessage, toolResultMessage }: ToolCallDisplayProps) {
  const toolCalls = toolCallMessage.tool_calls || [];
  
  // Check if the result contains a plot HTML
  const isPlotResult = (content: string) => {
    return content.includes('[PLOT_HTML]') && content.includes('[/PLOT_HTML]');
  };
  
  // Extract plot HTML from the result
  const extractPlotHtml = (content: string) => {
    const match = content.match(/\[PLOT_HTML\]([\s\S]*?)\[\/PLOT_HTML\]/);
    return match ? match[1] : null;
  };
  
  // Build a full HTML document for the iframe
  const buildPlotDocument = (plotHtml: string) => {
    return `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body { 
      margin: 0; 
      padding: 0; 
      background: transparent;
      overflow: hidden;
    }
    .plot-container {
      width: 100%;
      min-height: 400px;
    }
    .plotly-graph-div {
      width: 100% !important;
      height: 450px !important;
    }
  </style>
</head>
<body>
  ${plotHtml}
</body>
</html>`;
  };
  
  return (
    <div className="my-3 mx-4">
      {toolCalls.map((call, idx) => {
        const isPlot = toolResultMessage && isPlotResult(toolResultMessage.content);
        const plotHtml = isPlot ? extractPlotHtml(toolResultMessage.content) : null;
        
        return (
          <div key={call.id || idx} className="tool-call-block rounded-lg p-4 mb-2">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-accent text-sm font-mono">
                {call.name === 'create_plot' ? '📊' : '⚡'} Tool Call
              </span>
              <span className="text-gray-400 text-xs font-mono bg-black/30 px-2 py-0.5 rounded">
                {call.name}
              </span>
            </div>
            
            {/* Query/Args */}
            <div className="mb-3">
              <div className="text-xs text-gray-500 mb-1">Arguments:</div>
              <div className="bg-black/30 rounded p-2 font-mono text-sm text-gray-300">
                {typeof call.args === 'object' 
                  ? JSON.stringify(call.args, null, 2)
                  : String(call.args)
                }
              </div>
            </div>
            
            {/* Result */}
            {toolResultMessage && (
              <div>
                <div className="text-xs text-gray-500 mb-1">Result:</div>
                {plotHtml ? (
                  // Render plot in iframe - scripts execute inside iframe
                  <iframe
                    srcDoc={buildPlotDocument(plotHtml)}
                    className="w-full rounded-lg border-0"
                    style={{ height: '480px', background: 'transparent' }}
                    sandbox="allow-scripts"
                    title="Plot visualization"
                  />
                ) : (
                  // Render text result
                  <div className="bg-black/30 rounded p-2 font-mono text-xs text-gray-400 max-h-40 overflow-y-auto">
                    <pre className="whitespace-pre-wrap break-words">
                      {toolResultMessage.content}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
