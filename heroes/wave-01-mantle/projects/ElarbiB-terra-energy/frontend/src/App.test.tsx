import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

import App from './App';

vi.mock('./components/FloatingAssistant', () => ({
  default: () => <div data-testid="floating-assistant" />,
}));

describe('App', () => {
  beforeEach(() => {
    window.localStorage.setItem('terraenergy.lang', 'fr');
  });

  it('renders the hero presentation with the voice assistant', () => {
    const { container } = render(<App />);

    expect(screen.getByRole('heading', { name: /Évaluez le potentiel/ })).toBeInTheDocument();
    expect(screen.getByTestId('floating-assistant')).toBeInTheDocument();
  });

  it('shows the features, about and contact sections', () => {
    const { container } = render(<App />);

    expect(container.querySelector('#features')).toBeInTheDocument();
    expect(container.querySelector('#about')).toBeInTheDocument();
    expect(container.querySelector('#contact')).toBeInTheDocument();
    expect(container.querySelector('.navbar')).toBeInTheDocument();
    expect(container.querySelector('.footer')).toBeInTheDocument();
  });
});