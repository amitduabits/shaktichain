/**
 * Test setup file for Vitest
 * Configures testing environment with necessary mocks and utilities
 */

import { expect, afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';
import * as matchers from '@testing-library/jest-dom/matchers';

// Extend Vitest's expect with jest-dom matchers
expect.extend(matchers);

// Cleanup after each test
afterEach(() => {
  cleanup();
});

// Mock localStorage with an in-memory map so dual-mode auth can persist.
const memoryStore = new Map();
const localStorageMock = {
  getItem: vi.fn((key) => (memoryStore.has(key) ? memoryStore.get(key) : null)),
  setItem: vi.fn((key, value) => {
    memoryStore.set(String(key), String(value));
  }),
  removeItem: vi.fn((key) => {
    memoryStore.delete(key);
  }),
  clear: vi.fn(() => {
    memoryStore.clear();
  }),
};
globalThis.localStorage = localStorageMock;

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock ResizeObserver
globalThis.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));

// Mock IntersectionObserver
globalThis.IntersectionObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));

// Mock URL.createObjectURL
globalThis.URL.createObjectURL = vi.fn(() => 'mock-url');
globalThis.URL.revokeObjectURL = vi.fn();

// Reset all mocks after each test
afterEach(() => {
  vi.clearAllMocks();
  memoryStore.clear();
  localStorage.getItem.mockClear();
  localStorage.setItem.mockClear();
  localStorage.removeItem.mockClear();
});
