'use client';

import { useCallback, useEffect, useState } from 'react';
import { kbCommentsApi } from '@/lib/api/knowledgeBase';
import type { KbComment } from '@/lib/types';

interface CommentsPanelProps {
  documentId: number;
}

export default function CommentsPanel({ documentId }: CommentsPanelProps) {
  const [comments, setComments] = useState<KbComment[]>([]);
  const [newComment, setNewComment] = useState('');
  const [replyingTo, setReplyingTo] = useState<number | null>(null);
  const [replyText, setReplyText] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const loadComments = useCallback(async () => {
    try {
      const data = await kbCommentsApi.list(documentId);
      setComments(data);
    } catch (error) {
      console.error('Error loading comments:', error);
    }
  }, [documentId]);

  useEffect(() => {
    void loadComments();
  }, [loadComments]);

  const handleAddComment = async () => {
    if (!newComment.trim()) return;

    setIsLoading(true);
    try {
      await kbCommentsApi.create({
        document: documentId,
        content: newComment,
        parent_comment: null,
      });
      setNewComment('');
      await loadComments();
    } catch (error) {
      console.error('Error adding comment:', error);
      alert('Ошибка добавления комментария');
    } finally {
      setIsLoading(false);
    }
  };

  const handleReply = async (parentId: number) => {
    if (!replyText.trim()) return;

    setIsLoading(true);
    try {
      await kbCommentsApi.create({
        document: documentId,
        content: replyText,
        parent_comment: parentId,
      });
      setReplyText('');
      setReplyingTo(null);
      await loadComments();
    } catch (error) {
      console.error('Error adding reply:', error);
      alert('Ошибка добавления ответа');
    } finally {
      setIsLoading(false);
    }
  };

  const handleResolve = async (commentId: number) => {
    try {
      await kbCommentsApi.resolve(commentId);
      await loadComments();
    } catch (error) {
      console.error('Error resolving comment:', error);
    }
  };

  const handleUnresolve = async (commentId: number) => {
    try {
      await kbCommentsApi.unresolve(commentId);
      await loadComments();
    } catch (error) {
      console.error('Error unresolving comment:', error);
    }
  };

  const handleDelete = async (commentId: number) => {
    if (!confirm('Удалить комментарий?')) return;

    try {
      await kbCommentsApi.delete(commentId);
      await loadComments();
    } catch (error) {
      console.error('Error deleting comment:', error);
    }
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 sticky top-20">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-lg">Комментарии</h3>
        <span className="text-sm text-gray-500">{comments.length}</span>
      </div>

      <div className="mb-6">
        <textarea
          value={newComment}
          onChange={(e) => setNewComment(e.target.value)}
          placeholder="Добавить комментарий..."
          className="w-full px-3 py-2 border border-gray-300 rounded-lg resize-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          rows={3}
        />
        <button
          onClick={handleAddComment}
          disabled={isLoading || !newComment.trim()}
          className="mt-2 w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 transition-colors"
        >
          {isLoading ? 'Отправка...' : 'Отправить'}
        </button>
      </div>

      <div className="space-y-4 max-h-[600px] overflow-y-auto">
        {comments.filter((c) => !c.parent_comment).map((comment) => (
          <div key={comment.id} className="space-y-2">
            <div className={`p-3 rounded-lg ${comment.is_resolved ? 'bg-gray-50' : 'bg-blue-50'}`}>
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center text-sm font-medium">
                    {(comment.created_by?.username?.[0] ?? '?').toUpperCase()}
                  </div>
                  <div>
                    <div className="font-medium text-sm">{comment.created_by?.username ?? 'Пользователь'}</div>
                    <div className="text-xs text-gray-500">
                      {new Date(comment.created_at).toLocaleDateString('ru-RU', {
                        day: 'numeric',
                        month: 'short',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </div>
                  </div>
                </div>

                <div className="flex gap-1">
                  {!comment.is_resolved ? (
                    <button
                      onClick={() => handleResolve(comment.id)}
                      className="text-xs text-green-600 hover:text-green-700"
                      title="Отметить как решенное"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    </button>
                  ) : (
                    <button
                      onClick={() => handleUnresolve(comment.id)}
                      className="text-xs text-gray-600 hover:text-gray-700"
                      title="Открыть снова"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                    </button>
                  )}
                  <button
                    onClick={() => handleDelete(comment.id)}
                    className="text-xs text-red-600 hover:text-red-700"
                    title="Удалить"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              </div>

              <p className="text-sm whitespace-pre-wrap">{comment.content}</p>

              {comment.is_resolved && (
                <div className="mt-2 text-xs text-green-600 flex items-center gap-1">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  Решено
                </div>
              )}

              {!comment.is_resolved && (
                <button
                  onClick={() => setReplyingTo(comment.id)}
                  className="mt-2 text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1"
                >
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
                  </svg>
                  Ответить
                </button>
              )}
            </div>

            {replyingTo === comment.id && (
              <div className="ml-8 p-3 bg-gray-50 rounded-lg">
                <textarea
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  placeholder="Ваш ответ..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg resize-none focus:ring-2 focus:ring-blue-500 text-sm"
                  rows={2}
                />
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() => handleReply(comment.id)}
                    disabled={isLoading || !replyText.trim()}
                    className="px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:bg-gray-400"
                  >
                    Ответить
                  </button>
                  <button
                    onClick={() => {
                      setReplyingTo(null);
                      setReplyText('');
                    }}
                    className="px-3 py-1 text-gray-600 rounded text-sm hover:bg-gray-200"
                  >
                    Отмена
                  </button>
                </div>
              </div>
            )}

            {comment.replies && comment.replies.length > 0 && (
              <div className="ml-8 space-y-2">
                {comment.replies.map((reply) => (
                  <div key={reply.id} className="p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-full bg-gray-600 text-white flex items-center justify-center text-xs font-medium">
                          {(reply.created_by?.username?.[0] ?? '?').toUpperCase()}
                        </div>
                        <div>
                          <div className="font-medium text-sm">{reply.created_by?.username ?? 'Пользователь'}</div>
                          <div className="text-xs text-gray-500">
                            {new Date(reply.created_at).toLocaleDateString('ru-RU', {
                              day: 'numeric',
                              month: 'short',
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </div>
                        </div>
                      </div>
                      <button
                        onClick={() => handleDelete(reply.id)}
                        className="text-xs text-red-600 hover:text-red-700"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                    <p className="text-sm whitespace-pre-wrap">{reply.content}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}

        {comments.length === 0 && (
          <div className="text-center py-8">
            <svg className="w-12 h-12 mx-auto text-gray-300 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
            </svg>
            <p className="text-gray-500 text-sm">Пока нет комментариев</p>
          </div>
        )}
      </div>
    </div>
  );
}
