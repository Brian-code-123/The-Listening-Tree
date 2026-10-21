import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    return statSync(full).isDirectory() ? walk(full) : [full];
  });
}

// A cross-origin <link rel="stylesheet"> in <head> blocks first paint until that
// host answers (measured: ~0.5s of FCP on the login page, plus a font-swap CLS
// over the "good" threshold). Fonts and icons are bundled by next/font and
// @fortawesome/fontawesome-free instead.
describe('first paint does not wait on a third-party host', () => {
  const files = walk(path.join(__dirname, '../app')).filter((f) => /\.(tsx?|css)$/.test(f));

  it.each(files)('%s loads no stylesheet or font from another origin', (file) => {
    const src = readFileSync(file, 'utf8');
    expect(src).not.toMatch(/fonts\.(googleapis|gstatic)\.com|cdnjs\.cloudflare\.com|unpkg\.com|cdn\.jsdelivr\.net/);
    expect(src).not.toMatch(/<link[^>]+rel=["']stylesheet["'][^>]+href=["']https?:\/\//);
  });
});
