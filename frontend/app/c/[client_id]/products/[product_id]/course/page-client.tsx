'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';

import { ApiError, apiFetch } from '@/lib/api';
import type { ProductCourse } from '@/lib/types';

type RouteParams = { client_id: string; product_id: string };

type PublicCourseResponse = {
  course?: ProductCourse;
  access?: {
    is_contact_bound?: boolean;
    is_paid?: boolean;
  };
};

type PublicProductCoursePageClientProps = {
  resolvedClientId?: number;
  useCustomDomainPaths?: boolean;
};

export default function PublicProductCoursePage({
  resolvedClientId,
  useCustomDomainPaths = false,
}: PublicProductCoursePageClientProps = {}) {
  const { client_id: rawClientId, product_id: rawProductId } = useParams<Partial<RouteParams> & { product_id: string }>();
  const router = useRouter();
  const clientId = resolvedClientId ?? Number(rawClientId);
  const productId = Number(rawProductId);
  const productPath = useCustomDomainPaths ? `/products/${productId}` : `/c/${clientId}/products/${productId}`;
  const coursePath = `${productPath}/course`;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [course, setCourse] = useState<ProductCourse | null>(null);
  const [isPaid, setIsPaid] = useState(false);
  const progressCompleted = course?.progress?.completed_lessons ?? 0;
  const progressTotal = course?.progress?.total_lessons ?? 0;
  const rawProgressPercent = Number(course?.progress?.percent ?? 0);
  const progressPercent = Number.isFinite(rawProgressPercent)
    ? Math.min(100, Math.max(0, rawProgressPercent))
    : 0;
  const progressLabel = `Прогресс: ${progressCompleted} / ${progressTotal} (${progressPercent}%)`;

  useEffect(() => {
    const loadCourse = async () => {
      if (!Number.isFinite(clientId) || clientId <= 0 || !Number.isFinite(productId) || productId <= 0) {
        setError('Некорректный URL курса.');
        setLoading(false);
        return;
      }

      setLoading(true);
      setError(null);
      try {
        const payload = await apiFetch<PublicCourseResponse>(
          `/public/client-page/${clientId}/products/${productId}/course/`
        );
        setCourse(payload.course || null);
        setIsPaid(Boolean(payload.access?.is_paid));
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          const nextPath = coursePath;
          router.replace(`/login?tenant_id=${clientId}&next=${encodeURIComponent(nextPath)}`);
          return;
        }
        if (err instanceof ApiError && err.status === 404) {
          setError('Курс не найден или не опубликован.');
        } else {
          setError('Не удалось загрузить курс.');
        }
      } finally {
        setLoading(false);
      }
    };

    void loadCourse();
  }, [clientId, coursePath, productId, router]);

  if (loading) {
    return <div className="mx-auto max-w-4xl p-6 text-sm text-muted-foreground">Загрузка курса...</div>;
  }

  if (error || !course) {
    return (
      <div className="mx-auto max-w-4xl p-6 space-y-3">
        <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-700">{error || 'Курс не найден.'}</div>
        <Link href={productPath} className="inline-flex rounded-lg border px-3 py-2 text-sm hover:bg-accent">
          Вернуться к продукту
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl p-6 space-y-4">
      <div className="rounded-2xl border p-6 space-y-3">
        <h1 className="text-2xl font-semibold">{course.title}</h1>
        {course.description ? <p className="text-sm text-muted-foreground">{course.description}</p> : null}
        {course.cover_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={course.cover_url} alt={course.title} className="w-full max-h-72 object-cover rounded-xl border" />
        ) : null}
        <div className="flex items-center gap-3 text-sm">
          <div className="whitespace-nowrap text-muted-foreground">{progressLabel}</div>
          <div className="relative h-3 w-full overflow-hidden rounded-full border bg-muted/30">
            <div
              className="absolute inset-y-0 left-0 bg-primary/75 transition-[width] duration-300"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
        {!isPaid && (
          <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
            Доступ к полному курсу появится после оплаты продукта. Preview-уроки доступны сразу.
          </div>
        )}
      </div>

      <div className="space-y-3">
        {course.modules.map((module) => (
          <div key={module.id} className="rounded-xl border p-4 space-y-2">
            <div className="flex items-center justify-between gap-2">
              <div className="text-lg font-medium">{module.title}</div>
              {module.is_locked ? <span className="text-xs text-muted-foreground">Модуль закрыт</span> : null}
            </div>

            {module.lessons.length === 0 ? (
              <div className="text-sm text-muted-foreground">В модуле пока нет уроков.</div>
            ) : (
              <div className="space-y-2">
                {module.lessons.map((lesson) => {
                  const lessonAccepted = Boolean((lesson as { is_accepted?: boolean }).is_accepted);
                  const lessonStatus = lesson.is_locked
                    ? 'Закрыт'
                    : lessonAccepted
                      ? 'Принят'
                      : lesson.is_completed
                        ? 'Пройден'
                        : null;
                  const content = (
                    <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border p-3">
                      <div>
                        <div className="text-sm font-medium">{lesson.title}</div>
                        <div className="text-xs text-muted-foreground">{lesson.is_preview ? 'Preview' : 'Полный урок'}</div>
                      </div>
                      {lessonStatus ? <span className="text-xs text-muted-foreground">{lessonStatus}</span> : null}
                    </div>
                  );

                  if (lesson.is_locked) {
                    return <div key={lesson.id}>{content}</div>;
                  }

                  return (
                    <Link
                      key={lesson.id}
                      href={`${coursePath}/lessons/${lesson.id}`}
                      className="block rounded-lg transition-colors hover:bg-accent/40"
                    >
                      {content}
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
