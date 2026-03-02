// src/hooks/useData.ts
// Local shim: uses localStorage instead of Supabase
import { useState, useCallback } from 'react';
import { SavedReport } from '../data/mockSavedReports';
import { Message } from '../modules/mes/components/ChatInterface';
import { Sparkles } from 'lucide-react';

const LS_MESSAGES_PREFIX = 'nl2sql_chat_messages_';
const LS_SESSIONS_KEY = 'nl2sql_chat_sessions';
const LS_REPORTS_KEY = 'nl2sql_saved_reports';

// ── ChatSession ────────────────────────────────────────────────
export interface ChatSession {
  id: string;
  name: string;
  created_at: string;
}

// ── helpers ────────────────────────────────────────────────────
function loadSessions(): ChatSession[] {
  try {
    return JSON.parse(localStorage.getItem(LS_SESSIONS_KEY) || '[]');
  } catch {
    return [];
  }
}

function saveSessions(sessions: ChatSession[]): void {
  localStorage.setItem(LS_SESSIONS_KEY, JSON.stringify(sessions));
}

function loadMessages(sessionId: string): Message[] {
  try {
    const raw = localStorage.getItem(LS_MESSAGES_PREFIX + sessionId);
    if (!raw) return [];
    // Revive timestamp strings back to Date objects
    const arr = JSON.parse(raw);
    return arr.map((m: any) => ({ ...m, timestamp: new Date(m.timestamp) }));
  } catch {
    return [];
  }
}

function saveMessages(sessionId: string, messages: Message[]): void {
  localStorage.setItem(LS_MESSAGES_PREFIX + sessionId, JSON.stringify(messages));
}

function loadReports(): SavedReport[] {
  try {
    const raw = localStorage.getItem(LS_REPORTS_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return arr.map((r: any) => ({
      ...r,
      icon: Sparkles,
      created_at: r.created_at ? new Date(r.created_at) : undefined,
      updated_at: r.updated_at ? new Date(r.updated_at) : undefined,
    }));
  } catch {
    return [];
  }
}

function saveReports(reports: SavedReport[]): void {
  // Don't serialize icon (function), store the rest
  const serializable = reports.map(({ icon, ...rest }) => rest);
  localStorage.setItem(LS_REPORTS_KEY, JSON.stringify(serializable));
}

// ── hook ───────────────────────────────────────────────────────
export function useData() {
  const [savedReports, setSavedReports] = useState<SavedReport[]>(() => loadReports());
  const [loading] = useState(false);

  // ── chat messages ───────────────────────────────────────────
  const fetchChatMessages = useCallback(async (sessionId: string): Promise<Message[]> => {
    return loadMessages(sessionId);
  }, []);

  const addChatMessage = useCallback(async (sessionId: string, message: Message): Promise<Message> => {
    const existing = loadMessages(sessionId);
    const updated = [...existing.filter(m => m.id !== message.id), message];
    saveMessages(sessionId, updated);
    return message;
  }, []);

  // ── reports ─────────────────────────────────────────────────
  const refetchSavedReports = useCallback(async () => {
    const reports = loadReports();
    setSavedReports(reports);
  }, []);

  const createSavedReport = useCallback(async (reportData: Partial<SavedReport>): Promise<SavedReport> => {
    const newReport: SavedReport = {
      id: crypto.randomUUID(),
      name: reportData.name || '未命名报表',
      type: reportData.type || 'generic-report',
      icon: Sparkles,
      description: reportData.description,
      queryParams: reportData.queryParams,
      sqlQuery: reportData.sqlQuery,
      data: reportData.data,
      visualizationType: reportData.visualizationType,
      chartConfig: reportData.chartConfig,
      created_at: new Date(),
      updated_at: new Date(),
    };
    const existing = loadReports();
    const updated = [newReport, ...existing];
    saveReports(updated);
    setSavedReports(updated);
    return newReport;
  }, []);

  const deleteSavedReport = useCallback(async (id: string): Promise<void> => {
    const existing = loadReports();
    const updated = existing.filter(r => r.id !== id);
    saveReports(updated);
    setSavedReports(updated);
  }, []);

  // ── chat sessions ────────────────────────────────────────────
  const fetchChatSessions = useCallback(async (): Promise<ChatSession[]> => {
    const sessions = loadSessions();
    return sessions.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  }, []);

  const createChatSession = useCallback(async (id: string, name: string): Promise<ChatSession> => {
    const session: ChatSession = {
      id,
      name,
      created_at: new Date().toISOString(),
    };
    const existing = loadSessions();
    if (!existing.some(s => s.id === id)) {
      saveSessions([session, ...existing]);
    }
    return session;
  }, []);

  const fetchLatestChatSession = useCallback(async (): Promise<{ found: boolean; session?: ChatSession }> => {
    const sessions = loadSessions();
    if (sessions.length === 0) return { found: false };
    const sorted = sessions.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    return { found: true, session: sorted[0] };
  }, []);

  return {
    loading,
    savedReports,
    fetchChatMessages,
    addChatMessage,
    refetchSavedReports,
    createSavedReport,
    deleteSavedReport,
    fetchChatSessions,
    createChatSession,
    fetchLatestChatSession,
  };
}
