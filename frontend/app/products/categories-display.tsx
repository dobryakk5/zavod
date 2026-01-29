'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Trash2 } from 'lucide-react';

// Define the Category type
type Category = {
  id: number;
  name: string;
  description: string;
  color: string;
};

export function CategoriesDisplay() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [createCategoryName, setCreateCategoryName] = useState('');
  const [createCategoryDescription, setCreateCategoryDescription] = useState('');
  const [createCategoryColor, setCreateCategoryColor] = useState('#4A90E2');
  const [creatingCategory, setCreatingCategory] = useState(false);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      // Mock data for demonstration - in a real app, this would come from an API
      const mockCategories: Category[] = [
        { id: 1, name: 'VIP', description: 'Премиум клиенты с индивидуальным подходом', color: '#FFD700' },
        { id: 2, name: 'Стандарт', description: 'Регулярные клиенты', color: '#4A90E2' },
        { id: 3, name: 'Новички', description: 'Клиенты на пробном периоде', color: '#50C878' },
        { id: 4, name: 'Потенциальные', description: 'Лиды в воронке продаж', color: '#FFA500' },
      ];
      setCategories(mockCategories);
    } catch (err) {
      console.error('Failed to load categories', err);
      setError('Не удалось загрузить категории');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, []);

  const handleCreateCategory = async () => {
    const name = createCategoryName.trim();
    if (!name || creatingCategory) return;
    
    setCreatingCategory(true);
    setError(null);
    
    try {
      // In a real app, this would be an API call
      const newCategory: Category = {
        id: Date.now(), // Using timestamp as ID for demo
        name,
        description: createCategoryDescription,
        color: createCategoryColor
      };
      
      setCategories(prev => [newCategory, ...prev]);
      setCreateCategoryName('');
      setCreateCategoryDescription('');
      setCreateCategoryColor('#4A90E2');
    } catch (err) {
      console.error('Failed to create category', err);
      setError('Не удалось создать категорию');
    } finally {
      setCreatingCategory(false);
    }
  };

  const handleDeleteCategory = (categoryId: number) => {
    if (window.confirm('Вы уверены, что хотите удалить эту категорию?')) {
      setCategories(prev => prev.filter(cat => cat.id !== categoryId));
    }
  };

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-2xl font-semibold">Управление категориями</h2>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="flex flex-col gap-3 rounded-xl border bg-card/70 p-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-3">
          <Input
            placeholder="Название категории"
            value={createCategoryName}
            onChange={(e) => setCreateCategoryName(e.target.value)}
            className="w-full max-w-sm"
          />
          <Input
            placeholder="Описание"
            value={createCategoryDescription}
            onChange={(e) => setCreateCategoryDescription(e.target.value)}
            className="w-full max-w-sm"
          />
          <div className="flex items-center gap-2">
            <span>Цвет:</span>
            <input
              type="color"
              value={createCategoryColor}
              onChange={(e) => setCreateCategoryColor(e.target.value)}
              className="w-8 h-8 border rounded cursor-pointer"
            />
          </div>
          <Button onClick={handleCreateCategory} disabled={creatingCategory || !createCategoryName.trim()}>
            {creatingCategory ? 'Создание…' : 'Добавить категорию'}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">Введите название, описание и цвет, затем нажмите «Добавить категорию»</p>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Загружаем категории...</p>
      ) : categories.length === 0 ? (
        <p className="text-sm text-muted-foreground">Категории пока не добавлены.</p>
      ) : (
        <div className="rounded-xl border bg-card/70 shadow-sm">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Название</TableHead>
                <TableHead>Описание</TableHead>
                <TableHead>Цвет</TableHead>
                <TableHead className="w-[120px]">Действия</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {categories.map((category) => (
                <TableRow key={category.id}>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      <div 
                        className="w-4 h-4 rounded-full border" 
                        style={{ backgroundColor: category.color }}
                      ></div>
                      {category.name}
                    </div>
                  </TableCell>
                  <TableCell>{category.description}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <div 
                        className="w-4 h-4 rounded-full border" 
                        style={{ backgroundColor: category.color }}
                      ></div>
                      <span>{category.color}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-red-600 hover:text-red-700"
                      onClick={() => handleDeleteCategory(category.id)}
                      aria-label="Удалить категорию"
                      title="Удалить категорию"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}