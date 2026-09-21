import { describe, expect, it } from 'vitest';
import data from '../app/lib/translations-data.json';

const en = data.en as Record<string, string>;
const zh = data['zh-HK'] as Record<string, string>;

describe('translations', () => {
  it('has the same keys in en and zh-HK', () => {
    const missingInZh = Object.keys(en).filter((k) => !(k in zh));
    const missingInEn = Object.keys(zh).filter((k) => !(k in en));
    expect({ missingInZh, missingInEn }).toEqual({ missingInZh: [], missingInEn: [] });
  });

  it('has no empty values', () => {
    const empty = [...Object.entries(en), ...Object.entries(zh)].filter(([, v]) => !v.trim()).map(([k]) => k);
    expect(empty).toEqual([]);
  });
});
