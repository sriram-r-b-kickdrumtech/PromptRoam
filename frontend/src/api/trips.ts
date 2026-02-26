import axios from 'axios';
import type { WorkflowStatus, Message } from '../types';

const API_BASE = 'http://localhost:8000';

export const getStatus = async (threadId: string): Promise<any> => {
  const res = await axios.get(`${API_BASE}/state/${threadId}`);
  return res.data;
};

export const startTrip = async (threadId: string | null, message: string): Promise<any> => {
  const payload: any = { message };
  if (threadId) payload.thread_id = threadId;
  const res = await axios.post(`${API_BASE}/chat`, payload);
  return res.data;
};

export const submitClarification = async (threadId: string, answers: Record<string, string>): Promise<any> => {
  const res = await axios.post(`${API_BASE}/clarify`, { thread_id: threadId, answers });
  return res.data;
};

export const submitApproval = async (threadId: string, action: 'approve' | 'reject'): Promise<any> => {
  const res = await axios.post(`${API_BASE}/action`, { thread_id: threadId, action });
  return res.data;
};
