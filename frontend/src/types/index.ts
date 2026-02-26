export type AppStep = 'form' | 'clarifying' | 'researching' | 'approving' | 'complete' | 'error';

export interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export interface ClarificationQuestion {
  id: string;
  question: string;
  type?: 'text' | 'number' | 'date' | 'date_range' | 'multi_select';
  options?: string[];
  duration_days?: number;
}

export interface ExecutorResult {
  agent: string;
  task_id: string;
  result: any;
}

export interface TripLeg {
  id: string;
  summary: string;
  plan_reasoning: string;
  status: string;
}

export interface WorkflowStatus {
  step: AppStep;
  messages: Message[];
  interrupt_pending: boolean;
  awaiting_clarification: boolean;
  clarification_questions: ClarificationQuestion[];
  executor_results: ExecutorResult[];
  requested_trips: TripLeg[];
  validated_plans: Record<string, any>;
}
