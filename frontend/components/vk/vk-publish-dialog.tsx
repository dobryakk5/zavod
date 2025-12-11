'use client';

import { useState, type ChangeEvent, type FormEvent } from 'react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { vkApi } from '@/lib/api/vk';
import { toast } from 'sonner';
import type { VkIntegration } from '@/lib/types';

interface VkPublishDialogProps {
  integration: VkIntegration;
  onPublished?: () => void;
}

export function VkPublishDialog({ integration, onPublished }: VkPublishDialogProps) {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const resetForm = () => {
    setMessage('');
    setFiles([]);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!message.trim() && files.length === 0) {
      toast.error('Добавьте текст или изображение для публикации');
      return;
    }

    setSubmitting(true);
    try {
      await vkApi.publishPost({
        integration_id: integration.id,
        message,
        images: files,
      });
      toast.success('Пост отправлен в очередь публикации VK');
      setOpen(false);
      resetForm();
      onPublished?.();
    } catch (error) {
      console.error(error);
      toast.error('Не удалось отправить пост в VK');
    } finally {
      setSubmitting(false);
    }
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const nextFiles = event.target.files ? Array.from(event.target.files) : [];
    setFiles(nextFiles);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        setOpen(nextOpen);
        if (!nextOpen) {
          resetForm();
        }
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          Опубликовать пост
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Публикация в VK</DialogTitle>
          <DialogDescription>
            Пост будет опубликован в группе{' '}
            <strong>{integration.group_name || `ID ${integration.group_id}`}</strong>
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor={`vk-message-${integration.id}`}>Текст поста</Label>
            <Textarea
              id={`vk-message-${integration.id}`}
              placeholder="Расскажите, что нужно опубликовать..."
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              className="min-h-[120px]"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor={`vk-images-${integration.id}`}>
              Изображения (необязательно)
            </Label>
            <Input
              id={`vk-images-${integration.id}`}
              type="file"
              accept="image/*"
              multiple
              onChange={handleFileChange}
            />
            {files.length > 0 && (
              <p className="text-sm text-muted-foreground">
                Выбрано файлов: {files.length}
              </p>
            )}
          </div>

          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setOpen(false);
                resetForm();
              }}
            >
              Отмена
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? 'Публикация...' : 'Опубликовать'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
