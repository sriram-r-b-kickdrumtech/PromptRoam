import React, { useState } from 'react';
import type { WorkflowStatus, ExecutorResult, TripLeg } from '../types';
import { Check, X, Plane, Activity, CreditCard, AlertTriangle } from 'lucide-react';

interface Props {
  status: WorkflowStatus;
  onApprove: () => void;
  onEdit: () => void;
}

export default function Approval({ status, onApprove, onEdit }: Props) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const trip = status.requested_trips?.[0] as TripLeg | undefined;
  const results = status.executor_results || [];

  const handleAction = (action: 'approve' | 'edit') => {
    setIsSubmitting(true);
    if (action === 'approve') onApprove();
    else onEdit();
  };

  const getResult = (agent: string) => results.find((r: ExecutorResult) => r.agent === agent)?.result;

  const transport = getResult('transport');
  const accommodation = getResult('accommodation');
  const experience = getResult('experience');
  const financial = getResult('financial');

  const overBudget = financial && !financial.within_budget;

  return (
    <div className="max-w-4xl mx-auto w-full animate-in fade-in slide-in-from-bottom-4 duration-700 space-y-6">
      
      {overBudget && (
        <div className="bg-red-500/10 border border-red-500/30 p-5 rounded-2xl flex items-start gap-4 text-red-400">
          <AlertTriangle className="flex-shrink-0 mt-0.5" size={24} />
          <div>
            <h3 className="font-bold text-red-300">Budget Warning</h3>
            <p className="text-sm mt-1">The current estimated total is <strong>{financial.total}</strong>, which exceeds your maximum budget of <strong>{financial.max_budget}</strong>. You can approve this anyway, or reject to start over with different constraints.</p>
          </div>
        </div>
      )}

      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col">
        
        {/* Header */}
        <div className="bg-zinc-950 px-8 py-6 border-b border-zinc-800 flex flex-col md:flex-row md:justify-between md:items-center gap-6">
          <div>
            <span className="inline-block px-3 py-1 bg-brand-500/10 text-brand-400 text-xs font-bold uppercase tracking-wider rounded-lg mb-3">
              Draft Proposal
            </span>
            <h2 className="text-2xl font-bold text-zinc-100">{trip?.summary || 'Review Options'}</h2>
          </div>
          <div className="flex gap-3 shrink-0">
            <button
              onClick={() => handleAction('edit')}
              disabled={isSubmitting}
              className="px-5 py-2.5 text-zinc-300 bg-zinc-900 border border-zinc-700 rounded-xl hover:bg-zinc-800 hover:text-white flex items-center gap-2 font-bold transition-all disabled:opacity-50"
            >
              <X size={18} strokeWidth={2.5} /> Edit
            </button>
            <button
              onClick={() => handleAction('approve')}
              disabled={isSubmitting}
              className="px-6 py-2.5 bg-brand-600 hover:bg-brand-500 text-white rounded-xl flex items-center gap-2 font-bold shadow-[0_0_20px_rgba(14,165,233,0.3)] transition-all disabled:opacity-50"
            >
              <Check size={18} strokeWidth={3} /> Approve Plan
            </button>
          </div>
        </div>

        {/* Content Grid */}
        <div className="p-8 grid grid-cols-1 md:grid-cols-2 gap-6 bg-zinc-900/50">
          
          {/* Flights */}
          <div className="bg-zinc-950 border border-zinc-800/80 rounded-xl p-6">
            <div className="flex items-center gap-3 text-blue-400 font-bold mb-5 pb-4 border-b border-zinc-800">
              <div className="p-2 bg-blue-500/10 rounded-lg"><Plane size={20} /></div> Transport
            </div>
            {transport?.flights ? (
              <ul className="space-y-4">
                {transport.flights.slice(0, 3).map((f: any, i: number) => (
                  <li key={i} className="text-sm group">
                    <span className="font-bold text-zinc-200 group-hover:text-blue-400 transition-colors">{f.flight_name}</span>
                    <p className="text-zinc-500 mt-0.5">{f.origin} → {f.dest}</p>
                    {f.scheduled_departure && <p className="text-zinc-600 text-xs mt-1 font-mono">{f.scheduled_departure}</p>}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-zinc-600 italic">No exact flights found. Agent will estimate.</p>
            )}
          </div>

          {/* Hotels */}
          <div className="bg-zinc-950 border border-zinc-800/80 rounded-xl p-6">
            <div className="flex items-center gap-3 text-amber-400 font-bold mb-5 pb-4 border-b border-zinc-800">
              <div className="p-2 bg-amber-500/10 rounded-lg"><Hotel size={20} /></div> Accommodation
            </div>
            {accommodation?.hotels ? (
              <ul className="space-y-4">
                {accommodation.hotels.slice(0, 3).map((h: any, i: number) => (
                  <li key={i} className="text-sm group">
                    <span className="font-bold text-zinc-200 group-hover:text-amber-400 transition-colors">{h.name}</span>
                    <p className="text-zinc-500 mt-0.5">{h.location}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-zinc-600 italic">Agent will suggest appropriate lodging.</p>
            )}
          </div>

          {/* Activities */}
          <div className="bg-zinc-950 border border-zinc-800/80 rounded-xl p-6">
            <div className="flex items-center gap-3 text-emerald-400 font-bold mb-5 pb-4 border-b border-zinc-800">
              <div className="p-2 bg-emerald-500/10 rounded-lg"><Activity size={20} /></div> Experiences
            </div>
            {experience?.rag_suggestions ? (
              <ul className="space-y-4">
                {experience.rag_suggestions.slice(0, 3).map((a: any, i: number) => (
                  <li key={i} className="text-sm group">
                    <span className="font-bold text-zinc-200 group-hover:text-emerald-400 transition-colors">{a.metadata?.name || 'Activity'}</span>
                    <p className="text-zinc-500 mt-1 line-clamp-2 leading-relaxed">{a.content}</p>
                  </li>
                ))}
              </ul>
            ) : experience?.activities ? (
               <ul className="space-y-4">
                {experience.activities.slice(0, 3).map((a: any, i: number) => (
                  <li key={i} className="text-sm group">
                    <span className="font-bold text-zinc-200 group-hover:text-emerald-400 transition-colors">{a.name}</span>
                    <p className="text-zinc-500 mt-0.5">{a.location}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-zinc-600 italic">Agent will curate local highlights.</p>
            )}
          </div>

          {/* Budget */}
          <div className="bg-zinc-950 border border-zinc-800/80 rounded-xl p-6">
            <div className="flex items-center gap-3 text-indigo-400 font-bold mb-5 pb-4 border-b border-zinc-800">
              <div className="p-2 bg-indigo-500/10 rounded-lg"><CreditCard size={20} /></div> Financials
            </div>
            {financial ? (
              <div className="space-y-4">
                <div className="flex justify-between items-center text-sm p-3 bg-zinc-900 rounded-lg">
                  <span className="text-zinc-400">Estimated Total</span>
                  <span className={`font-mono text-lg font-bold ${overBudget ? 'text-red-400' : 'text-zinc-100'}`}>
                    {financial.total}
                  </span>
                </div>
                <div className="flex justify-between items-center text-sm px-3">
                  <span className="text-zinc-500">Max Budget</span>
                  <span className="font-mono text-zinc-400">{financial.max_budget}</span>
                </div>
                {financial.suggested_subset && (
                  <div className="mt-4 pt-4 border-t border-zinc-800">
                     <span className="text-xs font-bold text-zinc-500 uppercase tracking-wider block mb-2">Cost Breakdown</span>
                     {financial.suggested_subset.map((s: any, idx: number) => (
                       <div key={idx} className="flex justify-between text-xs text-zinc-400 mt-1">
                         <span className="capitalize">{s.category}</span>
                         <span className="font-mono">{s.cost}</span>
                       </div>
                     ))}
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-zinc-600 italic">Budget analysis unavailable.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// Local mock icon
const Hotel = ({ className, size }: { className?: string, size?: number }) => (
  <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M10 22v-6.57M14 22v-6.57M14 10h.01M10 10h.01M14 14h.01M10 14h.01M14 6h.01M10 6h.01M4 22V2M20 22V2M4 2h16"/>
  </svg>
)
