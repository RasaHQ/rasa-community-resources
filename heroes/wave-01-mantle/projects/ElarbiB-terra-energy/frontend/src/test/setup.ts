import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';
import React from 'react';

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
vi.stubGlobal('ResizeObserver', ResizeObserverMock);

class IntersectionObserverMock {
  constructor(callback: IntersectionObserverCallback) {
    this.callback = callback;
  }
  private callback: IntersectionObserverCallback;
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
  readonly root = null;
  readonly rootMargin = '';
  readonly thresholds = [0];
}
vi.stubGlobal('IntersectionObserver', IntersectionObserverMock);