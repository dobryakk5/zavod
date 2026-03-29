'use client';

import Link from 'next/link';
import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { ArrowLeftIcon } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { crmCategoriesApi, crmContactsApi, type Category, type Contact } from '@/lib/api/crm';
import { NewClientForm } from './new-clients-editor';

function NewClientPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [clients, setClients] = useState<Contact[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const openedFromDashboard = searchParams.get('from') === 'dashboard';

  useEffect(() => {
    let active = true;

    const loadData = async () => {
      setLoading(true);
      setError(null);
      try {
        const [contacts, nextCategories] = await Promise.all([
          crmContactsApi.list(),
          crmCategoriesApi.list(),
        ]);
        if (!active) {
          return;
        }
        setClients(contacts);
        setCategories(nextCategories);
      } catch (loadError) {
        console.error('Failed to load new client page data', loadError);
        if (!active) {
          return;
        }
        setError('Не удалось загрузить форму клиента.');
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    void loadData();
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="min-h-full bg-[#f5f4f0] p-4 sm:p-6">
      <div className="mx-auto max-w-3xl space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold text-[#1a1a18]">Новый клиент</h1>
            <p className="mt-1 text-sm text-[#73726c]">Создайте пустую карточку клиента и перейдите к её редактированию.</p>
          </div>
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 rounded-lg border border-[#d8d4ca] bg-white px-3 py-2 text-sm text-[#4f4b45] transition-colors hover:bg-[#f8f6f1]"
          >
            <ArrowLeftIcon className="h-4 w-4" />
            Назад
          </Link>
        </div>

        <Card className="border-[#e0ddd6] bg-white shadow-none">
          <CardHeader>
            <CardTitle>Карточка клиента</CardTitle>
            <CardDescription>
              Заполните имя, остальное - необязательно
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-sm text-[#73726c]">Загрузка формы клиента...</p>
            ) : error ? (
              <p className="text-sm text-red-500">{error}</p>
            ) : (
              <NewClientForm
                clients={clients}
                categories={categories}
                submitLabel="Создать клиента"
                helperText="Заполните имя клиента. При необходимости можно указать email, телефон, категорию и заметки."
                onSave={(createdClients) => {
                  const createdClient = createdClients[0];
                  if (!createdClient) {
                    return;
                  }
                  if (openedFromDashboard) {
                    router.push('/dashboard');
                    return;
                  }
                  router.push(`/contact/${createdClient.id}`);
                }}
              />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default function NewClientPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-full bg-[#f5f4f0] p-4 sm:p-6">
          <div className="mx-auto max-w-3xl space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h1 className="text-2xl font-semibold text-[#1a1a18]">Новый клиент</h1>
                <p className="mt-1 text-sm text-[#73726c]">Создайте пустую карточку клиента и перейдите к её редактированию.</p>
              </div>
              <Link
                href="/dashboard"
                className="inline-flex items-center gap-2 rounded-lg border border-[#d8d4ca] bg-white px-3 py-2 text-sm text-[#4f4b45] transition-colors hover:bg-[#f8f6f1]"
              >
                <ArrowLeftIcon className="h-4 w-4" />
                Назад
              </Link>
            </div>

            <Card className="border-[#e0ddd6] bg-white shadow-none">
              <CardHeader>
                <CardTitle>Карточка клиента</CardTitle>
                <CardDescription>
                  Заполните имя, остальное - необязательно
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-[#73726c]">Загрузка формы клиента...</p>
              </CardContent>
            </Card>
          </div>
        </div>
      }
    >
      <NewClientPageContent />
    </Suspense>
  );
}
