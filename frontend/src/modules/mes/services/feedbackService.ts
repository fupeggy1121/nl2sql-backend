// modules/mes/services/feedbackService.ts
// Local stub: stores feedback in localStorage
import { UserIntent } from './intentRecognizer';

export interface FeedbackData {
  messageId: string;
  feedbackType: 'helpful' | 'not_helpful' | 'incorrect' | 'other';
  rating: number;
  comment: string;
  query: string;
  response: string;
  intent?: UserIntent;
  resultData?: any[];
}

export interface FeedbackResponse {
  success: boolean;
  feedbackId?: string;
  message: string;
}

export interface FeedbackStats {
  totalFeedback: number;
  helpfulCount: number;
  notHelpfulCount: number;
  incorrectCount: number;
  otherCount: number;
  averageRating: number;
  recentFeedback: FeedbackData[];
}

const LS_KEY = 'nl2sql_feedback';

function loadFeedback(): FeedbackData[] {
  try {
    return JSON.parse(localStorage.getItem(LS_KEY) || '[]');
  } catch {
    return [];
  }
}

class FeedbackServiceClass {
  async submitFeedback(data: FeedbackData): Promise<FeedbackResponse> {
    const existing = loadFeedback();
    const updated = [data, ...existing];
    localStorage.setItem(LS_KEY, JSON.stringify(updated));
    return { success: true, feedbackId: data.messageId, message: '反馈已保存' };
  }

  async getIntentAccuracy(): Promise<number> {
    const feedback = loadFeedback();
    if (feedback.length === 0) return 0;
    const helpful = feedback.filter(f => f.feedbackType === 'helpful').length;
    return Math.round((helpful / feedback.length) * 100);
  }

  async getFeedbackStats(): Promise<FeedbackStats> {
    const feedback = loadFeedback();
    const totalFeedback = feedback.length;
    const helpfulCount = feedback.filter(f => f.feedbackType === 'helpful').length;
    const notHelpfulCount = feedback.filter(f => f.feedbackType === 'not_helpful').length;
    const incorrectCount = feedback.filter(f => f.feedbackType === 'incorrect').length;
    const otherCount = feedback.filter(f => f.feedbackType === 'other').length;
    const averageRating = totalFeedback > 0
      ? feedback.reduce((sum, f) => sum + f.rating, 0) / totalFeedback
      : 0;

    return {
      totalFeedback,
      helpfulCount,
      notHelpfulCount,
      incorrectCount,
      otherCount,
      averageRating,
      recentFeedback: feedback.slice(0, 10),
    };
  }
}

export const feedbackService = new FeedbackServiceClass();
