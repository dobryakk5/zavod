import { redirect } from 'next/navigation';

export default async function ArticleNewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  redirect(`/articles/${id}`);
}
