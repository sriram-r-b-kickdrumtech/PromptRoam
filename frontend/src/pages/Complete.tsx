import React, { useState } from 'react';
import { Download, RefreshCw, Map, Send } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import type { WorkflowStatus, Message } from '../types';

export default function Complete({ status, onGoHome, onEdit }: { status: WorkflowStatus, onGoHome: () => void, onEdit: (msg: string) => void }) {
  const [editPrompt, setEditPrompt] = useState('');
  
  // Find the last assistant message, which should be the final generated itinerary
  const itineraryMessage = [...status.messages].reverse().find((m: Message) => m.role === 'assistant')?.content;

  const downloadJson = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(status, null, 2));
    const a = document.createElement('a');
    a.href = dataStr;
    a.download = "promptroam_itinerary.json";
    a.click();
  };

  const handleEditSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (editPrompt.trim()) {
      onEdit(editPrompt.trim());
    }
  };

  return (
    <div className="max-w-4xl mx-auto w-full animate-in fade-in slide-in-from-bottom-4 duration-700 pb-20">
      <div className="bg-zinc-900 rounded-2xl shadow-2xl overflow-hidden border border-zinc-800">
        
        {/* Header */}
        <div className="bg-zinc-950 border-b border-zinc-800 p-8 flex flex-col md:flex-row justify-between md:items-end gap-6 relative overflow-hidden">
          <div className="absolute inset-0 opacity-20 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-brand-900 via-transparent to-transparent pointer-events-none" />
          
          <div className="relative z-10">
            <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-bold tracking-widest uppercase mb-4">
              <Map size={14} /> Itinerary Ready
            </span>
            <h1 className="text-3xl md:text-4xl font-extrabold text-zinc-100 tracking-tight">{status.requested_trips?.[0]?.summary || 'Your Travel Plan'}</h1>
            <p className="mt-2 text-zinc-400 font-medium">Carefully crafted by PromptRoam AI</p>
          </div>
          
          <div className="relative z-10 flex gap-3">
             <button
              onClick={downloadJson}
              className="flex items-center gap-2 px-5 py-2.5 bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 text-zinc-300 rounded-xl transition-colors text-sm font-bold shadow-sm"
            >
              <Download size={16} /> JSON
            </button>
            <button
              onClick={onGoHome}
              className="flex items-center gap-2 px-6 py-2.5 bg-zinc-800 hover:bg-zinc-700 text-white rounded-xl transition-all text-sm font-bold shadow-sm"
            >
              <RefreshCw size={16} /> New Trip
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-8 md:p-10 bg-zinc-900">
          <div className="prose prose-invert prose-brand max-w-none 
            prose-headings:font-bold prose-headings:tracking-tight 
            prose-h2:text-brand-400 prose-h2:border-b prose-h2:border-zinc-800 prose-h2:pb-2
            prose-h3:text-zinc-200
            prose-p:text-zinc-400 prose-p:leading-relaxed
            prose-li:text-zinc-400
            prose-strong:text-zinc-200
            prose-a:text-brand-500 hover:prose-a:text-brand-400
            marker:text-brand-500
          ">
            {itineraryMessage ? (
              <ReactMarkdown>{itineraryMessage}</ReactMarkdown>
            ) : (
              <div className="text-center py-20 text-zinc-500 italic flex flex-col items-center gap-4">
                 <Map size={48} className="text-zinc-800" />
                 <p>No itinerary content generated.</p>
              </div>
            )}
          </div>
        </div>
        
        {/* Iteration Chat Input */}
        <div className="bg-zinc-950 p-6 border-t border-zinc-800">
          <h3 className="text-zinc-300 font-bold mb-3 text-sm tracking-wide">WANT TO CHANGE SOMETHING?</h3>
          <form onSubmit={handleEditSubmit} className="relative">
            <input
              type="text"
              value={editPrompt}
              onChange={(e) => setEditPrompt(e.target.value)}
              placeholder="e.g. Can you change the hotel to something closer to the beach?"
              className="w-full pl-5 pr-14 py-4 bg-zinc-900 border border-zinc-700 rounded-xl text-zinc-100 focus:outline-none focus:ring-2 focus:ring-brand-500 transition-all placeholder-zinc-500"
            />
            <button
              type="submit"
              disabled={!editPrompt.trim()}
              className="absolute right-2 top-2 bottom-2 aspect-square bg-brand-600 hover:bg-brand-500 text-white rounded-lg flex items-center justify-center transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Send size={18} />
            </button>
          </form>
        </div>

      </div>
    </div>
  );
}
