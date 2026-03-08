'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { generateHTML } from '@tiptap/html';

import { ApiError, apiFetch } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { createKbExtensions } from '@/components/kb/tiptapExtensions';
import {
  buildCourseLessonEmbedUrl,
  normalizeCourseLessonContent,
  normalizeTiptapDoc,
} from '@/lib/courseLessonContent';
import type { ProductCourseLesson } from '@/lib/types';

type RouteParams = { client_id: string; product_id: string; lesson_id: string };

type PublicLessonResponse = ProductCourseLesson & {
  module?: {
    id: number;
    title: string;
    course?: {
      id: number;
      product_id: number;
      title: string;
    };
  };
};

type CourseLessonComment = {
  id: number;
  contact_id?: number | null;
  author_role: 'student' | 'curator' | 'system' | string;
  author_user_id?: number | null;
  author_name?: string;
  channel: 'courses' | 'telegram' | 'vk' | 'email' | string;
  message_text: string;
  metadata?: Record<string, unknown>;
  created_at: string;
  can_delete?: boolean;
};

export default function PublicProductCourseLessonPage() {
  const { client_id: rawClientId, product_id: rawProductId, lesson_id: rawLessonId } = useParams<RouteParams>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const clientId = Number(rawClientId);
  const productId = Number(rawProductId);
  const lessonId = Number(rawLessonId);
  const requestedCommentContactId = Number(searchParams.get('contact_id'));
  const hasRequestedCommentContactId = Number.isFinite(requestedCommentContactId) && requestedCommentContactId > 0;

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lesson, setLesson] = useState<PublicLessonResponse | null>(null);
  const [comments, setComments] = useState<CourseLessonComment[]>([]);
  const [commentDraft, setCommentDraft] = useState('');
  const [commentSaving, setCommentSaving] = useState(false);
  const [commentDeletingId, setCommentDeletingId] = useState<number | null>(null);
  const [commentError, setCommentError] = useState<string | null>(null);

  const tiptapExtensions = useMemo(() => createKbExtensions(), []);
  const commentsEndpoint = useMemo(() => {
    const basePath = `/public/client-page/${clientId}/products/${productId}/course/lessons/${lessonId}/comments/`;
    if (!hasRequestedCommentContactId) {
      return basePath;
    }
    return `${basePath}?contact_id=${requestedCommentContactId}`;
  }, [clientId, productId, lessonId, hasRequestedCommentContactId, requestedCommentContactId]);

  const loadComments = useCallback(async () => {
    try {
      const payload = await apiFetch<{ comments: CourseLessonComment[] }>(commentsEndpoint);
      setComments(Array.isArray(payload.comments) ? payload.comments : []);
      setCommentError(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setCommentError('Для комментариев нужно войти в аккаунт.');
      } else if (err instanceof ApiError && err.status === 403) {
        setCommentError('Комментарии недоступны, пока урок закрыт.');
      } else {
        setCommentError('Не удалось загрузить комментарии.');
      }
      setComments([]);
    }
  }, [commentsEndpoint]);

  const loadLesson = useCallback(async () => {
    if (!Number.isFinite(clientId) || clientId <= 0 || !Number.isFinite(productId) || productId <= 0 || !Number.isFinite(lessonId) || lessonId <= 0) {
      setError('Некорректный URL урока.');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const payload = await apiFetch<PublicLessonResponse>(
        `/public/client-page/${clientId}/products/${productId}/course/lessons/${lessonId}/`
      );
      setLesson(payload);
      await loadComments();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        const nextPath = `/c/${clientId}/products/${productId}/course/lessons/${lessonId}`;
        router.replace(`/login?tenant_id=${clientId}&next=${encodeURIComponent(nextPath)}`);
        return;
      }
      if (err instanceof ApiError && err.status === 403) {
        setError('Урок закрыт. Оплатите продукт или дождитесь открытия урока.');
      } else if (err instanceof ApiError && err.status === 404) {
        setError('Урок не найден.');
      } else {
        setError('Не удалось загрузить урок.');
      }
      setComments([]);
    } finally {
      setLoading(false);
    }
  }, [clientId, lessonId, loadComments, productId, router]);

  useEffect(() => {
    void loadLesson();
  }, [loadLesson]);

  const completeLesson = async () => {
    if (!lesson || saving) return;
    setSaving(true);
    setError(null);
    try {
      await apiFetch(`/public/client-page/${clientId}/products/${productId}/course/lessons/${lessonId}/complete/`, {
        method: 'POST',
      });
      await loadLesson();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError('Для отметки прохождения войдите как контакт через Telegram или VK.');
      } else if (err instanceof ApiError && err.status === 403) {
        setError('Урок пока недоступен для завершения.');
      } else {
        setError('Не удалось отметить урок как завершённый.');
      }
    } finally {
      setSaving(false);
    }
  };

  const submitComment = async () => {
    const text = commentDraft.trim();
    if (!text || commentSaving) return;
    setCommentSaving(true);
    setCommentError(null);
    try {
      const response = await apiFetch<{ ok: boolean; comment: CourseLessonComment }>(
        commentsEndpoint,
        {
          method: 'POST',
          body: hasRequestedCommentContactId
            ? { message_text: text, contact_id: requestedCommentContactId }
            : { message_text: text },
        }
      );
      if (response.comment) {
        setComments((prev) => [...prev, response.comment]);
      } else {
        await loadComments();
      }
      setCommentDraft('');
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setCommentError('Для отправки комментария войдите в аккаунт.');
      } else if (err instanceof ApiError && err.status === 403) {
        setCommentError('Комментарий недоступен, пока урок закрыт.');
      } else if (err instanceof ApiError && err.status === 400) {
        setCommentError('Не удалось отправить комментарий: проверьте выбранного ученика.');
      } else {
        setCommentError('Не удалось отправить комментарий.');
      }
    } finally {
      setCommentSaving(false);
    }
  };

  const deleteComment = async (commentId: number) => {
    if (commentDeletingId === commentId) return;
    setCommentDeletingId(commentId);
    setCommentError(null);
    try {
      const params = new URLSearchParams({ comment_id: String(commentId) });
      if (hasRequestedCommentContactId) {
        params.set('contact_id', String(requestedCommentContactId));
      }
      await apiFetch<void>(
        `/public/client-page/${clientId}/products/${productId}/course/lessons/${lessonId}/comments/?${params.toString()}`,
        { method: 'DELETE' }
      );
      setComments((prev) => prev.filter((item) => item.id !== commentId));
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setCommentError('Недостаточно прав для удаления этого комментария.');
      } else if (err instanceof ApiError && err.status === 404) {
        setCommentError('Комментарий уже удалён.');
      } else {
        setCommentError('Не удалось удалить комментарий.');
      }
    } finally {
      setCommentDeletingId(null);
    }
  };

  const renderedBlocks = useMemo(() => {
    if (!lesson) return [];

    const content = normalizeCourseLessonContent(lesson.content);
    return content.blocks.map((block) => {
      if (block.type === 'video') {
        const embedUrl = buildCourseLessonEmbedUrl({
          youtube_video_id: block.youtube_video_id || lesson.youtube_video_id || null,
          rutube_video_id: block.rutube_video_id || lesson.rutube_video_id || null,
          vk_owner_id: block.vk_owner_id || lesson.vk_owner_id || null,
          vk_video_id: block.vk_video_id || lesson.vk_video_id || null,
          vk_hash: block.vk_hash || lesson.vk_hash || null,
        });

        return {
          id: block.id,
          type: 'video' as const,
          embedUrl,
        };
      }

      if (block.type === 'image') {
        return {
          id: block.id,
          type: 'image' as const,
          imageUrl: (block.image_url || '').trim(),
          caption: (block.caption || '').trim(),
        };
      }

      let html = '';
      try {
        html = generateHTML(normalizeTiptapDoc(block.content), tiptapExtensions);
      } catch {
        html = '';
      }

      return {
        id: block.id,
        type: 'tiptap' as const,
        html,
      };
    });
  }, [lesson, tiptapExtensions]);

  if (loading) {
    return <div className="mx-auto max-w-4xl p-6 text-sm text-muted-foreground">Загрузка урока...</div>;
  }

  if (!lesson || error) {
    return (
      <div className="mx-auto max-w-4xl space-y-3 p-6">
        <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-700">{error || 'Урок недоступен.'}</div>
        <div className="flex gap-2">
          <Button type="button" variant="outline" onClick={() => router.push(`/c/${clientId}/products/${productId}/course`)}>
            К курсу
          </Button>
          <Button type="button" variant="secondary" onClick={() => void loadLesson()}>
            Обновить
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-6">
      <div className="flex flex-wrap gap-2">
        <Link href={`/c/${clientId}/products/${productId}/course`}>
          <Button type="button" variant="outline">К курсу</Button>
        </Link>
      </div>

      <div className="space-y-3 rounded-2xl border p-6">
        <div className="text-xs uppercase tracking-wide text-muted-foreground">{lesson.module?.title || 'Модуль'}</div>
        <h1 className="text-2xl font-semibold">{lesson.title}</h1>
        {lesson.is_preview ? <div className="text-xs text-muted-foreground">Preview-урок</div> : null}
      </div>

      <div className="space-y-4 rounded-2xl border p-6">
        {renderedBlocks.map((block) => {
          if (block.type === 'video') {
            if (!block.embedUrl) return null;
            return (
              <div key={block.id} className="overflow-hidden rounded-xl border">
                <div className="aspect-video w-full">
                  <iframe
                    src={block.embedUrl}
                    title={lesson.title}
                    className="h-full w-full"
                    allow="autoplay; encrypted-media; picture-in-picture"
                    allowFullScreen
                  />
                </div>
              </div>
            );
          }

          if (block.type === 'image') {
            if (!block.imageUrl) return null;
            return (
              <figure key={block.id} className="space-y-2 rounded-xl border p-2">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={block.imageUrl}
                  alt={block.caption || lesson.title}
                  className="max-h-[520px] w-full rounded-lg object-contain"
                />
                {block.caption ? (
                  <figcaption className="text-sm text-muted-foreground">{block.caption}</figcaption>
                ) : null}
              </figure>
            );
          }

          if (!block.html) {
            return null;
          }

          return (
            <div
              key={block.id}
              className="tiptap prose prose-slate max-w-none"
              dangerouslySetInnerHTML={{ __html: block.html }}
            />
          );
        })}
      </div>

      <div className="space-y-4 rounded-2xl border p-6">
        <div className="flex justify-end">
          <Button type="button" onClick={() => void completeLesson()} disabled={saving || lesson.is_completed}>
            {lesson.is_completed ? 'Урок уже завершён' : saving ? 'Сохраняем...' : 'Отметить как завершённый'}
          </Button>
        </div>

        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">Комментарии к уроку</h2>
          <div className="text-xs text-muted-foreground">{comments.length}</div>
        </div>

        {commentError ? (
          <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-700">{commentError}</div>
        ) : null}

        {comments.length === 0 ? (
          <div className="rounded-lg border p-3 text-sm text-muted-foreground">
            Пока нет комментариев. Напишите куратору первым.
          </div>
        ) : (
          <div className="space-y-2">
            {comments.map((item) => {
              const isStudent = item.author_role === 'student';
              const canDelete = Boolean(item.can_delete);
              const createdAt = new Date(item.created_at);
              const createdLabel = Number.isNaN(createdAt.getTime())
                ? item.created_at
                : createdAt.toLocaleString('ru-RU');
              return (
                <div
                  key={item.id}
                  className={`rounded-lg border px-3 py-2 ${isStudent ? 'bg-white' : 'bg-slate-50'}`}
                >
                  <div className="mb-1 flex items-center gap-2 text-[11px] text-muted-foreground">
                    <span>{item.author_name || (isStudent ? 'Ученик' : 'Куратор')}</span>
                    <span>·</span>
                    <span>{createdLabel}</span>
                    <span>·</span>
                    <span>{item.channel}</span>
                    {canDelete ? (
                      <>
                        <span>·</span>
                        <button
                          type="button"
                          className="text-xs text-red-600 hover:underline disabled:opacity-60"
                          onClick={() => void deleteComment(item.id)}
                          disabled={commentDeletingId === item.id}
                        >
                          {commentDeletingId === item.id ? 'Удаляем...' : 'Удалить'}
                        </button>
                      </>
                    ) : null}
                  </div>
                  <p className="whitespace-pre-wrap text-sm">{item.message_text}</p>
                </div>
              );
            })}
          </div>
        )}

        <div className="space-y-2">
          <textarea
            value={commentDraft}
            onChange={(event) => setCommentDraft(event.target.value)}
            placeholder="Ваш комментарий по уроку..."
            className="min-h-[92px] w-full rounded-md border p-3 text-sm outline-none focus:ring-1 focus:ring-ring"
            disabled={commentSaving}
          />
          <div className="flex justify-end">
            <Button type="button" onClick={() => void submitComment()} disabled={!commentDraft.trim() || commentSaving}>
              {commentSaving ? 'Отправка...' : 'Отправить комментарий'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
