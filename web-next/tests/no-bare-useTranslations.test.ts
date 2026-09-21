import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    return statSync(full).isDirectory() ? walk(full) : [full];
  });
}

describe('every page follows the session language', () => {
  const files = walk(path.join(__dirname, '../app')).filter((f) => /\.tsx?$/.test(f) && !f.endsWith('i18n.ts'));

  it.each(files)('%s does not call useTranslations() with no argument', (file) => {
    expect(readFileSync(file, 'utf8')).not.toMatch(/useTranslations\(\s*\)/);
  });
});
