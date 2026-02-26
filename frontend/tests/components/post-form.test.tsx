import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/components/ui/rich-text-editor', async () => {
  const ReactModule = await import('react');
  return {
    RichTextEditor: ({ value, onChange, placeholder, disabled, ...rest }: any) =>
      ReactModule.createElement('textarea', {
        value: value ?? '',
        placeholder,
        disabled,
        onChange: (e: any) => onChange(e.target.value),
        ...rest,
      }),
  };
});

vi.mock('@/components/ui/select', async () => {
  const ReactModule = await import('react');
  const SelectCtx = ReactModule.createContext<{
    value: string;
    setValue: (value: string) => void;
  } | null>(null);

  const Select = ({ defaultValue = '', onValueChange, children }: any) => {
    const [value, setValueState] = ReactModule.useState(defaultValue);
    const setValue = (nextValue: string) => {
      setValueState(nextValue);
      onValueChange?.(nextValue);
    };
    return ReactModule.createElement(SelectCtx.Provider, { value: { value, setValue } }, children);
  };

  const SelectTrigger = ({ children, ...props }: any) =>
    ReactModule.createElement('button', { type: 'button', ...props }, children);

  const SelectValue = ({ placeholder }: any) => {
    const ctx = ReactModule.useContext(SelectCtx);
    return ReactModule.createElement('span', null, ctx?.value || placeholder || '');
  };

  const SelectContent = ({ children, ...props }: any) => ReactModule.createElement('div', props, children);

  const SelectItem = ({ value, children, ...props }: any) => {
    const ctx = ReactModule.useContext(SelectCtx);
    return ReactModule.createElement(
      'button',
      {
        type: 'button',
        onClick: () => ctx?.setValue(value),
        ...props,
      },
      children
    );
  };

  return { Select, SelectTrigger, SelectValue, SelectContent, SelectItem };
});

describe('PostForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  const loadComponent = async () => {
    const mod = await import('@/components/posts/post-form');
    return mod.PostForm;
  };

  it('shows validation errors and does not submit invalid form', async () => {
    const onSubmit = vi.fn();
    const PostForm = await loadComponent();
    render(<PostForm onSubmit={onSubmit} />);

    fireEvent.click(screen.getByRole('button', { name: 'Создать' }));

    expect(await screen.findByText('Заголовок обязателен')).toBeInTheDocument();
    expect(await screen.findByText('Текст обязателен')).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('submits valid form values including selected status', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const PostForm = await loadComponent();
    render(<PostForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('Заголовок'), { target: { value: 'Пост о запуске' } });
    fireEvent.change(screen.getByLabelText('Цепляющий заголовок (для фото)'), { target: { value: 'Это работает!' } });
    fireEvent.change(screen.getByLabelText('Текст'), { target: { value: '<p>Текст поста</p>' } });
    fireEvent.change(screen.getByLabelText('Промпт для изображения (опционально)'), {
      target: { value: 'Светлая студия, человек с ноутбуком' },
    });

    fireEvent.click(screen.getByRole('button', { name: 'Статус' }));
    fireEvent.click(screen.getByRole('button', { name: 'Одобрен' }));

    fireEvent.click(screen.getByRole('button', { name: 'Создать' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1);
    });

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Пост о запуске',
        hook_title: 'Это работает!',
        text: '<p>Текст поста</p>',
        image_prompt: 'Светлая студия, человек с ноутбуком',
        status: 'approved',
      })
    );
  });

  it('resets values back to provided post defaults', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const PostForm = await loadComponent();

    render(
      <PostForm
        onSubmit={onSubmit}
        post={
          {
            id: 10,
            title: 'Исходный заголовок',
            hook_title: 'Хук',
            text: '<p>Исходный текст</p>',
            image_prompt: 'Исходный промпт',
            status: 'draft',
            created_at: '2026-02-26T00:00:00Z',
          } as any
        }
      />
    );

    const titleInput = screen.getByLabelText('Заголовок') as HTMLInputElement;
    const textInput = screen.getByLabelText('Текст') as HTMLTextAreaElement;

    fireEvent.change(titleInput, { target: { value: 'Новый заголовок' } });
    fireEvent.change(textInput, { target: { value: '<p>Новый текст</p>' } });

    expect(titleInput.value).toBe('Новый заголовок');
    expect(textInput.value).toBe('<p>Новый текст</p>');

    fireEvent.click(screen.getByRole('button', { name: 'Сбросить' }));

    await waitFor(() => {
      expect(titleInput.value).toBe('Исходный заголовок');
      expect(textInput.value).toBe('<p>Исходный текст</p>');
    });
  });

  it('disables submit and shows loading label when loading=true', async () => {
    const PostForm = await loadComponent();
    render(<PostForm onSubmit={vi.fn()} loading />);

    const submitButton = screen.getByRole('button', { name: 'Сохранение...' });
    expect(submitButton).toBeDisabled();
  });
});
