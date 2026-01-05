'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { mindMapsApi } from '@/lib/api/mindmaps';
import { websitesApi, type WebsiteScanDetail, type WebsiteScanPage } from '@/lib/api/websites';
import type { MindMapDetail, MindNode, MindNodeProperty } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

type WordstatItem = { word: string; count: number };

const normalizeUrl = (url?: string | null): string => {
  if (!url) return '';
  return url.replace(/\/+$/, '');
};

const normalizeWordstats = (wordstats?: Array<{ word?: unknown; count?: unknown }>): WordstatItem[] => {
  if (!wordstats?.length) return [];
  return wordstats
    .map((item) => {
      const word = String(item.word ?? '').trim();
      const countRaw = item.count;
      const count = Number.isFinite(Number(countRaw)) ? Number(countRaw) : 0;
      return word ? { word, count } : null;
    })
    .filter((item): item is WordstatItem => Boolean(item));
};

const wordstatsFromNode = (node: MindNode): WordstatItem[] => {
  const meta = node.meta as Record<string, unknown> | undefined;
  const metaWordstats = Array.isArray(meta?.wordstats)
    ? normalizeWordstats(meta?.wordstats as Array<{ word?: unknown; count?: unknown }>)
    : [];
  if (metaWordstats.length) return metaWordstats;

  const props = (node.properties ?? []) as MindNodeProperty[];
  if (!props.length) return [];
  return props
    .map((prop) => {
      const word = String(prop.title ?? '').trim();
      const count = Number.isFinite(Number(prop.value)) ? Number(prop.value) : 0;
      return word ? { word, count } : null;
    })
    .filter((item): item is WordstatItem => Boolean(item));
};

type NodeInfo = {
  title?: string;
  wordstats: WordstatItem[];
};

const buildNodeInfoByUrl = (mindMap: MindMapDetail): Record<string, NodeInfo> => {
  const map: Record<string, NodeInfo> = {};
  mindMap.nodes.forEach((node) => {
    const meta = node.meta as Record<string, unknown> | undefined;
    const urlCandidate =
      typeof meta?.page_url === 'string'
        ? meta.page_url
        : typeof meta?.url === 'string'
          ? meta.url
          : typeof meta?.metric_type === 'string'
            ? meta.metric_type
            : '';
    if (!urlCandidate) return;
    const wordstats = wordstatsFromNode(node);
    const title =
      typeof meta?.page_title === 'string' && meta.page_title.trim()
        ? meta.page_title.trim()
        : node.text?.trim()
          ? node.text.trim()
          : undefined;
    if (!wordstats.length && !title) return;
    const normalized = normalizeUrl(urlCandidate);
    const entry: NodeInfo = { title, wordstats };
    map[urlCandidate] = entry;
    if (normalized) map[normalized] = entry;
  });
  return map;
};

const formatWordStats = (wordstats?: WordstatItem[]): string => {
  if (!wordstats?.length) return '—';
  const topWords = [...wordstats]
    .sort((a, b) => b.count - a.count)
    .slice(0, 5)
    .map((item) => `${item.word} (${item.count})`);
  return topWords.join(', ');
};

const getPageHeading = (page: WebsiteScanPage, fallbackTitle?: string): string => {
  const headings = page.headings as Record<string, unknown> | undefined;
  const h1 = headings?.h1;
  if (Array.isArray(h1) && h1.length > 0) {
    const first = String(h1[0] ?? '').trim();
    if (first) return first;
  }
  if (typeof h1 === 'string' && h1.trim()) return h1.trim();
  if (fallbackTitle?.trim()) return fallbackTitle.trim();
  return page.title?.trim() || page.url;
};

export default function WebsiteScanListPage() {
  const params = useParams<{ scanId: string }>();
  const router = useRouter();
  const scanId = useMemo(() => {
    if (!params?.scanId) return null;
    return Array.isArray(params.scanId) ? params.scanId[0] : params.scanId;
  }, [params?.scanId]);

  const [scan, setScan] = useState<WebsiteScanDetail | null>(null);
  const [pages, setPages] = useState<WebsiteScanPage[]>([]);
  const [nodeInfoByUrl, setNodeInfoByUrl] = useState<Record<string, NodeInfo>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    const load = async () => {
      if (!scanId) return;
      setLoading(true);
      setError(null);
      try {
        const [scanData, pagesData] = await Promise.all([
          websitesApi.getScan(scanId),
          websitesApi.listPages(scanId)
        ]);
        if (!isMounted) return;
        setScan(scanData);
        setPages(pagesData);
        if (scanData.mind_map_id) {
          try {
            const mindMap = await mindMapsApi.detail(scanData.mind_map_id);
            if (!isMounted) return;
            setNodeInfoByUrl(buildNodeInfoByUrl(mindMap));
          } catch (mapError) {
            if (isMounted) setNodeInfoByUrl({});
          }
        } else {
          setNodeInfoByUrl({});
        }
      } catch (err) {
        if (!isMounted) return;
        setError('Не удалось загрузить список страниц.');
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    load();

    return () => {
      isMounted = false;
    };
  }, [scanId]);

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="space-y-2">
          <Button variant="ghost" size="sm" onClick={() => router.push('/analytics?tab=website')}>
            <ArrowLeft className="h-4 w-4 mr-1" />
            Назад к аналитике
          </Button>
          <div>
            <h1 className="text-2xl font-bold">Список страниц</h1>
            <p className="text-sm text-muted-foreground">
              {scan?.base_url ? `Сайт: ${scan.base_url}` : 'Скан сайта'}
            </p>
          </div>
        </div>
        <div className="text-sm text-muted-foreground">
          {pages.length ? `Найдено страниц: ${pages.length}` : ' '}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Загружаем список страниц
        </div>
      ) : error ? (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      ) : pages.length === 0 ? (
        <p className="text-sm text-muted-foreground">Страницы не найдены.</p>
      ) : (
        <div className="rounded-lg border bg-white shadow-sm">
          <Table>
            <TableHeader>
              <TableRow className="bg-gray-50">
                <TableHead>Название страницы</TableHead>
                <TableHead>URL</TableHead>
                <TableHead>Слова</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pages.map((page) => {
                const normalizedUrl = normalizeUrl(page.url);
                const nodeInfo = nodeInfoByUrl[normalizedUrl] || nodeInfoByUrl[page.url];
                const wordstats = nodeInfo?.wordstats?.length ? nodeInfo.wordstats : page.wordstats;
                return (
                <TableRow key={page.id}>
                  <TableCell className="font-medium text-gray-900">
                    {getPageHeading(page, nodeInfo?.title)}
                  </TableCell>
                  <TableCell className="text-sm text-blue-600">
                    <a
                      href={page.url}
                      target="_blank"
                      rel="noreferrer"
                      className="break-all hover:underline"
                    >
                      {page.url}
                    </a>
                  </TableCell>
                  <TableCell className="text-sm text-gray-600">
                    {formatWordStats(wordstats)}
                  </TableCell>
                </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
