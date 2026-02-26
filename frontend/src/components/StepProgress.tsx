import React from 'react';
import type { AppStep } from '../types';
import { Check } from 'lucide-react';

const STEPS: { key: AppStep; label: string; desc: string }[] = [
  { key: 'form', label: 'Start', desc: 'Set parameters' },
  { key: 'clarifying', label: 'Clarify', desc: 'Missing details' },
  { key: 'researching', label: 'Research', desc: 'Agent search' },
  { key: 'approving', label: 'Approve', desc: 'Review plan' },
  { key: 'complete', label: 'Done', desc: 'Get itinerary' },
];

const STEP_ORDER: AppStep[] = ['form', 'clarifying', 'researching', 'approving', 'complete', 'error'];

export default function StepProgress({ current, horizontal = false }: { current: AppStep, horizontal?: boolean }) {
  const currentIdx = STEP_ORDER.indexOf(current === 'error' ? 'form' : current);
  
  if (horizontal) {
    return (
      <div className="flex items-center gap-2">
        {STEPS.map((s, i) => {
          const done = i < currentIdx;
          const active = i === currentIdx;
          if (i === 0) return null; // Skip 'Start' on mobile horizontal
          return (
            <div key={s.key} className="flex items-center gap-2 flex-1">
              <div className={`
                h-1.5 flex-1 rounded-full transition-all duration-500
                ${done ? 'bg-brand-500' : active ? 'bg-brand-400 animate-pulse shadow-[0_0_10px_rgba(56,189,248,0.5)]' : 'bg-zinc-800'}
              `} />
            </div>
          );
        })}
      </div>
    );
  }

  // Vertical layout for sidebar
  return (
    <div className="flex flex-col relative before:absolute before:inset-y-6 before:left-[11px] before:w-0.5 before:bg-zinc-800">
      {STEPS.map((s, i) => {
        const done = i < currentIdx;
        const active = i === currentIdx;
        
        return (
          <div key={s.key} className="flex gap-4 relative py-4 group">
            {/* Connection Line active state */}
            {done && i < STEPS.length - 1 && (
              <div className="absolute top-10 left-[11px] w-0.5 h-full bg-brand-500 z-0" />
            )}

            {/* Circle Node */}
            <div className={`
              w-6 h-6 rounded-full border-2 flex items-center justify-center flex-shrink-0 z-10 bg-zinc-900 transition-all duration-300
              ${done ? 'border-brand-500 bg-brand-500 text-white' : 
                active ? 'border-brand-400 text-brand-400 shadow-[0_0_15px_rgba(56,189,248,0.3)]' : 
                'border-zinc-700 text-transparent'}
            `}>
              {done ? <Check size={12} strokeWidth={3} /> : <div className={`w-2 h-2 rounded-full ${active ? 'bg-brand-400 animate-ping' : 'bg-zinc-700'}`} />}
            </div>

            {/* Text */}
            <div className="flex flex-col pt-0.5">
              <span className={`text-sm font-bold transition-colors ${active ? 'text-zinc-100' : done ? 'text-zinc-300' : 'text-zinc-600'}`}>
                {s.label}
              </span>
              <span className={`text-xs ${active ? 'text-zinc-400' : 'text-zinc-600'}`}>
                {s.desc}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
