import React from 'react';
import type { AppStep, WorkflowStatus } from '../types';
import { Search, Map, Calendar, Plane, Layers } from 'lucide-react';

interface Props {
  step: AppStep;
  status: WorkflowStatus | null;
}

export default function StatusPolling({ step }: Props) {
  const isResearching = step === 'researching';

  return (
    <div className="max-w-xl mx-auto w-full text-center flex flex-col items-center justify-center min-h-[50vh] animate-in fade-in duration-1000">
      
      <div className="relative w-32 h-32 mb-10 flex items-center justify-center">
        {/* Radar/Pulse effect */}
        <div className="absolute inset-0 border-2 border-brand-500/20 rounded-full animate-[ping_3s_ease-out_infinite]" />
        <div className="absolute inset-4 border border-brand-400/30 rounded-full animate-[ping_2s_ease-out_infinite_0.5s]" />
        
        <div className="relative z-10 w-20 h-20 bg-zinc-900 border-2 border-zinc-800 rounded-2xl flex items-center justify-center shadow-[0_0_30px_rgba(14,165,233,0.15)] overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-b from-brand-500/10 to-transparent" />
          {isResearching ? (
            <Search size={36} className="text-brand-400 animate-pulse drop-shadow-[0_0_8px_rgba(56,189,248,0.8)]" />
          ) : (
            <Layers size={36} className="text-brand-400 animate-bounce drop-shadow-[0_0_8px_rgba(56,189,248,0.8)]" />
          )}
        </div>
      </div>
      
      <h2 className="text-3xl font-extrabold text-zinc-100 mb-4 tracking-tight">
        {isResearching ? 'Agents are researching...' : 'Synthesizing itinerary...'}
      </h2>
      <p className="text-zinc-400 mb-12 max-w-sm mx-auto text-lg leading-relaxed">
        {isResearching 
          ? 'Our AI agents are parallel-searching real-time APIs to find the best options.'
          : 'Compiling all research into a beautiful, budget-checked day-by-day plan.'}
      </p>

      {isResearching && (
        <div className="grid grid-cols-3 gap-4 w-full">
          <div className="flex flex-col items-center gap-3 p-5 bg-zinc-900 border border-zinc-800 rounded-xl shadow-inner relative overflow-hidden group">
            <div className="absolute top-0 left-0 w-full h-1 bg-blue-500/50" />
            <Plane className="text-blue-400" size={24} />
            <span className="text-xs font-bold text-zinc-300 uppercase tracking-wider">Transport</span>
          </div>
          <div className="flex flex-col items-center gap-3 p-5 bg-zinc-900 border border-zinc-800 rounded-xl shadow-inner relative overflow-hidden group">
            <div className="absolute top-0 left-0 w-full h-1 bg-amber-500/50" />
            <Hotel className="text-amber-400" size={24} />
            <span className="text-xs font-bold text-zinc-300 uppercase tracking-wider">Lodging</span>
          </div>
          <div className="flex flex-col items-center gap-3 p-5 bg-zinc-900 border border-zinc-800 rounded-xl shadow-inner relative overflow-hidden group">
            <div className="absolute top-0 left-0 w-full h-1 bg-emerald-500/50" />
            <Calendar className="text-emerald-400" size={24} />
            <span className="text-xs font-bold text-zinc-300 uppercase tracking-wider">Activities</span>
          </div>
        </div>
      )}
    </div>
  );
}

// Local mock icon for Hotel since it's not exported from lucide-react in StatusPolling context
const Hotel = ({ className, size }: { className?: string, size?: number }) => (
  <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M10 22v-6.57M14 22v-6.57M14 10h.01M10 10h.01M14 14h.01M10 14h.01M14 6h.01M10 6h.01M4 22V2M20 22V2M4 2h16"/>
  </svg>
)
