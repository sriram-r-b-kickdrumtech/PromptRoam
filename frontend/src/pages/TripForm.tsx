import React, { useState } from 'react';
import { Send, MapPin, Sparkles, Wallet } from 'lucide-react';

export default function TripForm({ onSubmit }: { onSubmit: (msg: string) => void }) {
  const [prompt, setPrompt] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    setIsSubmitting(true);
    onSubmit(prompt);
  };

  const suggestions = [
    "2 days in Goa under 15k with beach vibes",
    "A week in Kerala focusing on culture and food",
    "Weekend getaway to Rishikesh for adventure",
  ];

  return (
    <div className="max-w-2xl mx-auto w-full animate-in fade-in slide-in-from-bottom-4 duration-700">
      <div className="mb-10">
        <h2 className="text-4xl font-extrabold text-zinc-100 mb-3 tracking-tight">
          Where to next?
        </h2>
        <p className="text-zinc-400 text-lg">
          Tell our multi-agent system your destination, dates, and budget. It will handle the rest.
        </p>
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl shadow-2xl overflow-hidden p-6 relative group">
        <div className="absolute inset-0 bg-gradient-to-br from-brand-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none" />
        
        <form onSubmit={handleSubmit} className="relative z-10">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="e.g., A 3-day spiritual trip to Varanasi under ₹20,000..."
            className="w-full min-h-[160px] p-6 text-lg bg-zinc-950 border border-zinc-800 rounded-xl text-zinc-100 focus:border-brand-500 focus:ring-1 focus:ring-brand-500 transition-all resize-none placeholder-zinc-600 outline-none"
            disabled={isSubmitting}
            autoFocus
          />
          <button
            type="submit"
            disabled={isSubmitting || !prompt.trim()}
            className="absolute bottom-4 right-4 px-6 py-2.5 bg-brand-600 hover:bg-brand-500 text-white rounded-lg font-bold flex items-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-brand-500/25"
          >
            {isSubmitting ? (
              <span className="flex items-center gap-2">Planning <span className="flex gap-1"><span className="w-1 h-1 bg-white rounded-full animate-bounce"/> <span className="w-1 h-1 bg-white rounded-full animate-bounce delay-75"/> <span className="w-1 h-1 bg-white rounded-full animate-bounce delay-150"/></span></span>
            ) : (
              <>Send <Send size={16} strokeWidth={2.5} /></>
            )}
          </button>
        </form>

        <div className="mt-8 pt-6 border-t border-zinc-800/50 relative z-10">
          <p className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-4">Try asking for:</p>
          <div className="flex flex-col gap-3">
            {suggestions.map((s, i) => (
              <button
                key={i}
                onClick={() => setPrompt(s)}
                className="text-left px-4 py-3 rounded-xl text-sm text-zinc-400 bg-zinc-950/50 hover:bg-zinc-800 hover:text-zinc-200 border border-zinc-800/50 hover:border-zinc-700 transition-all flex items-center gap-4 group/btn"
              >
                <div className="p-2 rounded-lg bg-zinc-900 group-hover/btn:bg-zinc-800 transition-colors">
                  {i === 0 && <MapPin size={16} className="text-brand-400" />}
                  {i === 1 && <Sparkles size={16} className="text-amber-400" />}
                  {i === 2 && <Wallet size={16} className="text-emerald-400" />}
                </div>
                {s}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
