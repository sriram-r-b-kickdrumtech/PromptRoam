import React, { useEffect, useState } from 'react';
import type { AppStep, WorkflowStatus } from './types';
import { startTrip, submitClarification, submitApproval, getStatus } from './api/trips';
import TripForm from './pages/TripForm';
import Clarification from './pages/Clarification';
import StatusPolling from './pages/StatusPolling';
import Approval from './pages/Approval';
import Complete from './pages/Complete';
import StepProgress from './components/StepProgress';
import { Compass } from 'lucide-react';

export default function App() {
  const [appStep, setAppStep] = useState<AppStep>('form');
  const [threadId, setThreadId] = useState('');
  const [status, setStatus] = useState<WorkflowStatus | null>(null);
  const [error, setError] = useState('');

  const generateThreadId = () => `sess-${Math.random().toString(36).substring(2, 9)}`;

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const tid = params.get('thread_id') || localStorage.getItem('thread_id') || '';
    if (tid) {
      setThreadId(tid);
      syncThreadIdToUrl(tid);
      // try to restore status on refresh
      getStatus(tid)
        .then((res) => {
          setStatus(res);
          updateStepFromStatus(res);
        })
        .catch(() => {});
    }
  }, []);

  const syncThreadIdToUrl = (tid: string) => {
    const params = new URLSearchParams(window.location.search);
    params.set('thread_id', tid);
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.replaceState({}, '', newUrl);
    localStorage.setItem('thread_id', tid);
  };

  const handleStart = async (msg: string) => {
    try {
      const tid = threadId || generateThreadId();
      setThreadId(tid);
      syncThreadIdToUrl(tid);
      setAppStep('researching');
      
      const res = await startTrip(tid, msg);
      setStatus(res);
      updateStepFromStatus(res);
    } catch (e: any) {
      setError(e.message || "Failed to start trip");
      setAppStep('error');
    }
  };

  const handleEdit = async (msg: string) => {
    try {
      setAppStep('researching');
      
      const res = await startTrip(threadId, msg);
      setStatus(res);
      updateStepFromStatus(res);
    } catch (e: any) {
      setError(e.message || "Failed to edit trip");
      setAppStep('error');
    }
  };

  const handleClarification = async (answers: Record<string, string>) => {
    try {
      setAppStep('researching');
      const res = await submitClarification(threadId, answers);
      setStatus(res);
      updateStepFromStatus(res);
    } catch (e: any) {
      setError(e.message || "Failed to submit details");
      setAppStep('error');
    }
  };

  const handleApprovalAction = async (action: 'approve' | 'reject') => {
    try {
      setAppStep(action === 'approve' ? 'generating' : 'form');
      const res = await submitApproval(threadId, action);
      if (action === 'approve') {
         setStatus(res);
         updateStepFromStatus(res);
      } else {
         goHome();
      }
    } catch (e: any) {
      setError(e.message || "Action failed");
      setAppStep('error');
    }
  };

  const updateStepFromStatus = (s: WorkflowStatus) => {
    if (s.step === 'complete') {
      setAppStep('complete');
      return;
    }
    if (s.step === 'approving' || s.interrupt_pending || (s.executor_results && s.executor_results.length > 0)) {
      setAppStep('approving');
      return;
    }
    if (s.step === 'awaiting_clarification' || s.awaiting_clarification) {
      setAppStep('clarifying');
      return;
    }
  };

  const goHome = () => {
    setAppStep('form');
    setThreadId('');
    setStatus(null);
    setError('');
  };

  const goEdit = () => {
    setAppStep('form');
    setError('');
  };

  return (
    <div className="min-h-screen bg-zinc-950 font-sans text-zinc-100 flex flex-col md:flex-row selection:bg-brand-500/30">
      
      {/* Sidebar */}
      <aside className="w-full md:w-72 bg-zinc-900 border-b md:border-b-0 md:border-r border-zinc-800 flex flex-col flex-shrink-0">
        <div className="p-6">
          <button onClick={goHome} className="flex items-center gap-3 hover:opacity-80 transition-opacity focus:outline-none w-full">
            <div className="bg-brand-500 text-white p-2 rounded-xl shadow-[0_0_15px_rgba(14,165,233,0.3)]">
              <Compass size={24} />
            </div>
            <div className="text-left">
              <h1 className="text-xl font-bold tracking-tight text-white">Prompt<span className="text-brand-400">Roam</span></h1>
              {threadId && <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider mt-0.5">ID: {threadId}</p>}
            </div>
          </button>
        </div>
        
        <div className="flex-1 p-6 overflow-y-auto hidden md:block">
          {appStep !== 'form' && appStep !== 'error' && (
            <StepProgress current={appStep} />
          )}
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col max-h-screen overflow-y-auto">
        {/* Mobile progress bar (only shows if not form/error) */}
        <div className="md:hidden p-4 bg-zinc-900/50 border-b border-zinc-800">
           {appStep !== 'form' && appStep !== 'error' && (
            <StepProgress current={appStep} horizontal />
          )}
        </div>

        <div className="flex-1 p-4 md:p-10 lg:p-12 w-full max-w-5xl mx-auto relative">
          
          {appStep === 'form' && <TripForm onSubmit={handleStart} />}
          
          {appStep === 'clarifying' && status?.clarification_questions && (
            <Clarification questions={status.clarification_questions} onSubmit={handleClarification} />
          )}
          
          {(appStep === 'researching' || appStep === 'generating') && (
            <StatusPolling step={appStep} status={status} />
          )}
          
          {appStep === 'approving' && status && (
            <Approval status={status} onApprove={() => handleApprovalAction('approve')} onEdit={goEdit} />
          )}
          
          {appStep === 'complete' && status && (
            <Complete status={status} onGoHome={goHome} onEdit={handleEdit} />
          )}

          {appStep === 'error' && (
            <div className="max-w-lg mx-auto text-center mt-20 p-8 bg-zinc-900 rounded-2xl border border-red-900/50 shadow-2xl">
               <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-red-500/10 text-red-500 mb-6 border border-red-500/20">
                 <span className="text-2xl">⚠️</span>
               </div>
               <h2 className="text-xl font-bold text-zinc-100 mb-3">Something went wrong</h2>
               <p className="text-zinc-400 mb-8 p-4 bg-zinc-950 rounded-lg text-sm border border-zinc-800 font-mono text-left overflow-x-auto">{error}</p>
               <button onClick={goHome} className="px-6 py-2.5 bg-zinc-100 text-zinc-900 rounded-lg font-bold hover:bg-white transition-colors w-full">
                 Start Over
               </button>
            </div>
          )}
        </div>
      </main>

    </div>
  );
}
