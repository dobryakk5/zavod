import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Button } from '@/components/ui/button';

describe('Button', () => {
  it('renders a button element with default styles', () => {
    render(<Button>Save</Button>);

    const button = screen.getByRole('button', { name: 'Save' });
    expect(button).toBeInTheDocument();
    expect(button).toHaveClass('inline-flex');
    expect(button).toHaveClass('bg-primary');
    expect(button).toHaveClass('h-10');
  });

  it('renders child element when asChild is enabled', () => {
    render(
      <Button asChild variant="link">
        <a href="/docs">Docs</a>
      </Button>
    );

    const link = screen.getByRole('link', { name: 'Docs' });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/docs');
    expect(link).toHaveClass('text-primary');
    expect(link.tagName).toBe('A');
  });
});
