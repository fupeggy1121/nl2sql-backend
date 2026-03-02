import { useState } from 'react';
import { X, Send, Loader2, ThumbsUp, ThumbsDown } from 'lucide-react';
import { feedbackService, FeedbackData } from '../services/feedbackService';
import { UserIntent } from '../services/intentRecognizer';

interface FeedbackFormProps {
  messageId: string;
  query: string;
  response: string;
  intent?: UserIntent;
  resultData?: any[];
  onClose: () => void;
  onSubmit?: (success: boolean) => void;
}

type FeedbackType = 'helpful' | 'not_helpful' | 'incorrect' | 'other';

export function FeedbackForm({
  messageId,
  query,
  response,
  intent,
  resultData,
  onClose,
  onSubmit
}: FeedbackFormProps) {
  const [step, setStep] = useState<'type' | 'detail'>('type');
  const [feedbackType, setFeedbackType] = useState<FeedbackType | null>(null);
  const [rating, setRating] = useState(3);
  const [comment, setComment] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitMessage, setSubmitMessage] = useState('');

  const handleTypeSelect = (type: FeedbackType) => {
    setFeedbackType(type);
    setStep('detail');
  };

  const handleSubmit = async () => {
    if (!feedbackType) return;

    setIsSubmitting(true);

    const feedbackData: FeedbackData = {
      messageId,
      feedbackType,
      rating,
      comment,
      query,
      response,
      intent,
      resultData
    };

    const result = await feedbackService.submitFeedback(feedbackData);

    setIsSubmitting(false);
    setSubmitMessage(result.message);

    if (result.success) {
      setTimeout(() => {
        onSubmit?.(true);
        onClose();
      }, 1500);
    }
  };

  const feedbackTypeLabels: Record<FeedbackType, string> = {
    helpful: '有帮助',
    not_helpful: '没帮助',
    incorrect: '结果不准确',
    other: '其他问题'
  };

  const feedbackTypeDescriptions: Record<FeedbackType, string> = {
    helpful: '这个回复很有用',
    not_helpful: '回复没有解决问题',
    incorrect: '数据或结果不准确',
    other: '其他反馈'
  };

  if (submitMessage) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-white rounded-2xl p-8 max-w-sm shadow-2xl">
          <div className="text-center space-y-4">
            <div className="w-16 h-16 mx-auto bg-green-100 rounded-full flex items-center justify-center">
              <ThumbsUp className="w-8 h-8 text-green-600" />
            </div>
            <h3 className="text-lg font-bold text-gray-900">反馈已提交</h3>
            <p className="text-gray-600">{submitMessage}</p>
            <div className="h-1 bg-gradient-to-r from-green-500 to-blue-500 rounded-full" />
          </div>
        </div>
      </div>
    );
  }

  if (step === 'type') {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
        <div className="bg-white rounded-2xl p-6 max-w-sm shadow-2xl">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-bold text-gray-900">您对这个回复满意吗？</h3>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <X className="w-6 h-6" />
            </button>
          </div>

          <div className="space-y-3">
            <button
              onClick={() => handleTypeSelect('helpful')}
              className="w-full p-4 rounded-xl border-2 border-gray-200 hover:border-green-500 hover:bg-green-50 transition-all text-left"
            >
              <div className="flex items-center space-x-3">
                <ThumbsUp className="w-5 h-5 text-green-600" />
                <div>
                  <p className="font-semibold text-gray-900">{feedbackTypeLabels.helpful}</p>
                  <p className="text-xs text-gray-500">{feedbackTypeDescriptions.helpful}</p>
                </div>
              </div>
            </button>

            <button
              onClick={() => handleTypeSelect('not_helpful')}
              className="w-full p-4 rounded-xl border-2 border-gray-200 hover:border-yellow-500 hover:bg-yellow-50 transition-all text-left"
            >
              <div className="flex items-center space-x-3">
                <ThumbsDown className="w-5 h-5 text-yellow-600" />
                <div>
                  <p className="font-semibold text-gray-900">{feedbackTypeLabels.not_helpful}</p>
                  <p className="text-xs text-gray-500">{feedbackTypeDescriptions.not_helpful}</p>
                </div>
              </div>
            </button>

            <button
              onClick={() => handleTypeSelect('incorrect')}
              className="w-full p-4 rounded-xl border-2 border-gray-200 hover:border-red-500 hover:bg-red-50 transition-all text-left"
            >
              <div className="flex items-center space-x-3">
                <div className="w-5 h-5 flex items-center justify-center text-red-600 font-bold">!</div>
                <div>
                  <p className="font-semibold text-gray-900">{feedbackTypeLabels.incorrect}</p>
                  <p className="text-xs text-gray-500">{feedbackTypeDescriptions.incorrect}</p>
                </div>
              </div>
            </button>

            <button
              onClick={() => handleTypeSelect('other')}
              className="w-full p-4 rounded-xl border-2 border-gray-200 hover:border-blue-500 hover:bg-blue-50 transition-all text-left"
            >
              <div className="flex items-center space-x-3">
                <div className="w-5 h-5 flex items-center justify-center text-blue-600 font-bold">?</div>
                <div>
                  <p className="font-semibold text-gray-900">{feedbackTypeLabels.other}</p>
                  <p className="text-xs text-gray-500">{feedbackTypeDescriptions.other}</p>
                </div>
              </div>
            </button>
          </div>

          <p className="text-xs text-gray-500 mt-6 text-center">
            您的反馈将帮助我们改进AI系统
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl p-6 max-w-md shadow-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-gray-900">反馈详情</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              反馈类型
            </label>
            <div className="px-4 py-2 bg-gray-100 rounded-lg text-sm text-gray-700">
              {feedbackType ? feedbackTypeLabels[feedbackType] : '未选择'}
            </div>
          </div>

          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-3">
              满意度评分
            </label>
            <div className="flex gap-2">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  onClick={() => setRating(star)}
                  className={`px-4 py-2 rounded-lg font-bold transition-all ${
                    rating >= star
                      ? 'bg-gradient-to-r from-yellow-400 to-yellow-500 text-white'
                      : 'bg-gray-200 text-gray-500 hover:bg-gray-300'
                  }`}
                >
                  ★
                </button>
              ))}
            </div>
            <p className="text-xs text-gray-500 mt-2">
              {rating === 1 && '非常不满意'}
              {rating === 2 && '不满意'}
              {rating === 3 && '一般'}
              {rating === 4 && '满意'}
              {rating === 5 && '非常满意'}
            </p>
          </div>

          <div>
            <label htmlFor="comment" className="block text-sm font-semibold text-gray-700 mb-2">
              详细说明（可选）
            </label>
            <textarea
              id="comment"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="请说明您的反馈原因或建议..."
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none h-24 text-sm"
            />
            <p className="text-xs text-gray-500 mt-1">
              {comment.length}/200
            </p>
          </div>

          <div className="bg-blue-50 rounded-lg p-4 text-xs text-blue-700 border border-blue-200">
            <p className="font-semibold mb-1">您的反馈包括：</p>
            <ul className="space-y-1 list-disc list-inside">
              <li>原始查询</li>
              <li>AI回复</li>
              <li>识别的意图</li>
              {resultData && <li>查询结果摘要</li>}
            </ul>
          </div>
        </div>

        <div className="flex gap-3 mt-6">
          <button
            onClick={() => setStep('type')}
            className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium"
          >
            返回
          </button>
          <button
            onClick={handleSubmit}
            disabled={isSubmitting || !feedbackType}
            className="flex-1 px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-lg hover:from-blue-700 hover:to-indigo-700 disabled:from-gray-300 disabled:to-gray-400 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2 font-medium"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>提交中...</span>
              </>
            ) : (
              <>
                <Send className="w-4 h-4" />
                <span>提交反馈</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
