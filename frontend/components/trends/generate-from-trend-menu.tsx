'use client';

import { useState } from 'react';
import { trendsApi } from '@/lib/api/trends';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useRole } from '@/lib/hooks';
import { toast } from 'sonner';
import { Sparkles } from 'lucide-react';

interface GenerateFromTrendMenuProps {
  trendId: number;
}

export function GenerateFromTrendMenu({ trendId }: GenerateFromTrendMenuProps) {
  const { canEdit } = useRole();
  const [showStoryDialog, setShowStoryDialog] = useState(false);
  const [episodeCount, setEpisodeCount] = useState(3);
  const [loading, setLoading] = useState(false);

  const handleGeneratePost = async () => {
    setLoading(true);
    try {
      await trendsApi.generatePost(trendId);
      toast.success('Генерация поста запущена');
    } catch (error) {
      toast.error('Ошибка при генерации поста');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateStory = async () => {
    setLoading(true);
    try {
      await trendsApi.generateStory(trendId, { episode_count: episodeCount });
      toast.success('Генерация истории запущена');
      setShowStoryDialog(false);
    } catch (error) {
      toast.error('Ошибка при генерации истории');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button size="sm" variant="default" disabled={!canEdit || loading}>
            <Sparkles className="h-4 w-4 mr-1" />
            Сгенерировать
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem onClick={handleGeneratePost}>
            Сгенерировать пост
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => setShowStoryDialog(true)}>
            Сгенерировать историю
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={showStoryDialog} onOpenChange={setShowStoryDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Генерация истории</DialogTitle>
            <DialogDescription>
              История - это серия связанных постов (эпизодов)
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <Label htmlFor="episodeCount">Количество эпизодов</Label>
            <Input
              id="episodeCount"
              type="number"
              min={2}
              max={10}
              value={episodeCount}
              onChange={(e) => setEpisodeCount(parseInt(e.target.value) || 3)}
              className="mt-2"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowStoryDialog(false)}>
              Отмена
            </Button>
            <Button onClick={handleGenerateStory} disabled={loading}>
              {loading ? 'Генерация...' : 'Сгенерировать'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
