'use client';

import { useState, useEffect } from 'react';
import { socialAccountsApi } from '@/lib/api/socialAccounts';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Plus, Trash2, Edit } from 'lucide-react';
import { toast } from 'sonner';
import { useRole } from '@/lib/hooks';
import type { SocialAccount } from '@/lib/types';

export function SocialAccountsManager() {
  const { canEdit } = useRole();
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadAccounts();
  }, []);

  const loadAccounts = async () => {
    setLoading(true);
    try {
      const data = await socialAccountsApi.list();
      setAccounts(data);
    } catch (error) {
      toast.error('Не удалось загрузить аккаунты');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Вы уверены, что хотите удалить этот аккаунт?')) {
      return;
    }

    try {
      await socialAccountsApi.delete(id);
      toast.success('Аккаунт успешно удален');
      await loadAccounts();
    } catch (error) {
      toast.error('Ошибка при удалении аккаунта');
    }
  };

  const getPlatformBadgeColor = (platform: string) => {
    switch (platform) {
      case 'instagram':
        return 'bg-pink-500 text-white';
      case 'telegram':
        return 'bg-blue-500 text-white';
      case 'youtube':
        return 'bg-red-500 text-white';
      default:
        return 'bg-gray-500 text-white';
    }
  };

  if (loading) {
    return <div className="text-center py-8">Загрузка...</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">Социальные аккаунты</h2>
        {canEdit && (
          <Button size="sm">
            <Plus className="h-4 w-4 mr-2" />
            Добавить аккаунт
          </Button>
        )}
      </div>

      {accounts.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          Нет подключенных аккаунтов
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Платформа</TableHead>
              <TableHead>Название</TableHead>
              <TableHead>Имя пользователя</TableHead>
              <TableHead>Статус</TableHead>
              <TableHead className="text-right">Действия</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {accounts.map((account) => (
              <TableRow key={account.id}>
                <TableCell>
                  <Badge className={getPlatformBadgeColor(account.platform)}>
                    {account.platform}
                  </Badge>
                </TableCell>
                <TableCell className="font-medium">{account.name}</TableCell>
                <TableCell className="text-gray-600">
                  {account.username || '—'}
                </TableCell>
                <TableCell>
                  {account.is_active ? (
                    <Badge variant="outline" className="text-green-600 border-green-600">
                      Активен
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="text-gray-400 border-gray-400">
                      Неактивен
                    </Badge>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  {canEdit && (
                    <div className="flex gap-2 justify-end">
                      <Button variant="ghost" size="sm">
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(account.id)}
                      >
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    </div>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
