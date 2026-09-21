import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'node',
    include: ['tests/unit/**/*.test.{js,ts}'],
    globals: true,
    coverage: {
      reporter: ['text', 'html'],
    },
  },
});