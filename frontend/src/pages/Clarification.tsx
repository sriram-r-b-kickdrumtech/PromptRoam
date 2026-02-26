import React, { useState } from 'react';
import type { ClarificationQuestion } from '../types';
import { HelpCircle, ArrowRight } from 'lucide-react';

interface Props {
  questions: ClarificationQuestion[];
  onSubmit: (answers: Record<string, string>) => void;
}

export default function Clarification({ questions, onSubmit }: Props) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    onSubmit(answers);
  };

  return (
    <div className="max-w-2xl mx-auto w-full animate-in fade-in slide-in-from-bottom-4 duration-700">
      
      <div className="bg-zinc-900 border border-amber-500/30 shadow-[0_0_30px_rgba(245,158,11,0.05)] rounded-2xl overflow-hidden">
        <div className="bg-amber-500/10 p-6 border-b border-amber-500/20 flex items-start gap-4">
          <div className="p-3 bg-amber-500/20 rounded-xl text-amber-400 shadow-inner">
            <HelpCircle size={24} strokeWidth={2.5} />
          </div>
          <div>
            <h2 className="text-xl font-bold text-amber-100 tracking-tight">I need a bit more info</h2>
            <p className="text-amber-400/80 mt-1 text-sm">
              To craft the perfect itinerary, our agents need these specific details before they can start searching.
            </p>
          </div>
        </div>
        
        <form onSubmit={handleSubmit} className="p-8 space-y-6">
          {questions.map((q) => (
            <div key={q.id} className="group">
              <label className="block text-sm font-bold text-zinc-300 mb-2 group-focus-within:text-brand-400 transition-colors">
                {q.question}
              </label>
              <input
                type="text"
                required
                value={answers[q.id] || ''}
                onChange={(e) => setAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
                className="w-full px-5 py-3.5 bg-zinc-950 border border-zinc-800 text-zinc-100 rounded-xl focus:ring-1 focus:ring-brand-500 focus:border-brand-500 outline-none transition-all placeholder-zinc-700 shadow-inner"
                placeholder="Type your answer here..."
              />
            </div>
          ))}
          
          <div className="pt-6 flex justify-end">
            <button
              type="submit"
              disabled={isSubmitting || Object.keys(answers).length !== questions.length || Object.values(answers).some(v => !v.trim())}
              className="px-8 py-3.5 bg-amber-500 hover:bg-amber-400 text-zinc-950 font-bold rounded-xl flex items-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-[0_4px_14px_rgba(245,158,11,0.2)] hover:shadow-[0_4px_20px_rgba(245,158,11,0.4)]"
            >
              {isSubmitting ? 'Updating...' : <>Continue <ArrowRight size={18} strokeWidth={2.5} /></>}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
