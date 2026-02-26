import React, { useMemo, useState } from 'react';
import type { ClarificationQuestion } from '../types';
import { HelpCircle, ArrowRight } from 'lucide-react';
import { DayPicker } from 'react-day-picker';
import type { DateRange } from 'react-day-picker';
import 'react-day-picker/dist/style.css';

interface Props {
  questions: ClarificationQuestion[];
  onSubmit: (answers: Record<string, string>) => void;
}

export default function Clarification({ questions, onSubmit }: Props) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [dateRanges, setDateRanges] = useState<Record<string, DateRange | undefined>>({});
  const [durationDays, setDurationDays] = useState<Record<string, number>>({});
  const [multi, setMulti] = useState<Record<string, Set<string>>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    const payload: Record<string, string> = { ...answers };
    for (const [qid, range] of Object.entries(dateRanges)) {
      if (range?.from) {
        const from = range.from.toISOString().slice(0, 10);
        const to = range.to ? range.to.toISOString().slice(0, 10) : from;
        payload[qid] = `${from} to ${to}`;
        if (durationDays[qid]) {
          payload["duration_days"] = String(durationDays[qid]);
        }
      }
    }
    for (const [qid, set] of Object.entries(multi)) {
      if (set.size > 0) {
        payload[qid] = Array.from(set).join(', ');
      }
    }
    onSubmit(payload);
  };

  const requiredFilled = useMemo(() => {
    return questions.every((q) => {
      if (q.type === 'date_range') {
        const r = dateRanges[q.id];
        return !!(r && r.from && r.to);
      }
      if (q.type === 'multi_select') {
        return (multi[q.id]?.size || 0) > 0;
      }
      return !!(answers[q.id] && answers[q.id].trim());
    });
  }, [questions, answers, dateRanges, multi]);

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
              {q.type === 'multi_select' && q.options ? (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {q.options.map((opt) => {
                    const isChecked = multi[q.id]?.has(opt) || false;
                    return (
                      <label key={opt} className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${isChecked ? 'border-brand-500 bg-brand-500/10' : 'border-zinc-800 bg-zinc-950'} cursor-pointer`}>
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={(e) => {
                            setMulti((prev) => {
                              const next = new Set(prev[q.id] || []);
                              if (e.target.checked) next.add(opt);
                              else next.delete(opt);
                              return { ...prev, [q.id]: next };
                            });
                          }}
                          className="accent-brand-500"
                        />
                        <span className="text-sm text-zinc-200 capitalize">{opt}</span>
                      </label>
                    );
                  })}
                </div>
              ) : q.type === 'date_range' ? (
                <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-3">
                  <div className="flex items-center gap-3 mb-3">
                    <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider">
                      Duration (days)
                    </label>
                    <input
                      type="number"
                      min={1}
                      value={durationDays[q.id] ?? q.duration_days ?? 2}
                      onChange={(e) => {
                        const val = Math.max(1, parseInt(e.target.value || '1', 10));
                        setDurationDays((prev) => ({ ...prev, [q.id]: val }));
                        const current = dateRanges[q.id];
                        if (current?.from) {
                          const from = current.from;
                          const to = new Date(from);
                          to.setDate(to.getDate() + val - 1);
                          setDateRanges((prev) => ({ ...prev, [q.id]: { from, to } }));
                        }
                      }}
                      className="w-24 px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-lg text-zinc-100"
                    />
                  </div>
                  <DayPicker
                    mode="range"
                    selected={dateRanges[q.id]}
                    onSelect={(range) => {
                      if (!range?.from) {
                        setDateRanges((prev) => ({ ...prev, [q.id]: range }));
                        return;
                      }
                      const days = durationDays[q.id] ?? q.duration_days;
                      if (days) {
                        const from = range.from;
                        const to = new Date(from);
                        to.setDate(to.getDate() + days - 1);
                        setDateRanges((prev) => ({ ...prev, [q.id]: { from, to } }));
                        return;
                      }
                      setDateRanges((prev) => ({ ...prev, [q.id]: range }));
                    }}
                    numberOfMonths={1}
                    className="text-zinc-200 rdp-themed"
                  />
                  {(durationDays[q.id] ?? q.duration_days) ? (
                    <p className="text-xs text-zinc-500 mt-2">
                      Select a range of {durationDays[q.id] ?? q.duration_days} days.
                    </p>
                  ) : null}
                </div>
              ) : (
                <input
                  type={q.type === 'number' ? 'number' : 'text'}
                  required
                  value={answers[q.id] || ''}
                  onChange={(e) => setAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
                  className="w-full px-5 py-3.5 bg-zinc-950 border border-zinc-800 text-zinc-100 rounded-xl focus:ring-1 focus:ring-brand-500 focus:border-brand-500 outline-none transition-all placeholder-zinc-700 shadow-inner"
                  placeholder="Type your answer here..."
                />
              )}
            </div>
          ))}
          
          <div className="pt-6 flex justify-end">
            <button
              type="submit"
              disabled={isSubmitting || !requiredFilled}
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
