import { describe, expect, test } from 'vitest';
import { hexToRgba } from './BboxOverlay.jsx';

describe('hexToRgba', () => {
  test('converts a #RRGGBB hex string to an rgba() string with the given alpha', () => {
    expect(hexToRgba('#EAF3DE', 0.25)).toBe('rgba(234, 243, 222, 0.25)');
  });

  test('handles hex strings without a leading #', () => {
    expect(hexToRgba('FCEBEB', 0.25)).toBe('rgba(252, 235, 235, 0.25)');
  });

  test('handles black and white extremes', () => {
    expect(hexToRgba('#000000', 0.5)).toBe('rgba(0, 0, 0, 0.5)');
    expect(hexToRgba('#FFFFFF', 0.5)).toBe('rgba(255, 255, 255, 0.5)');
  });
});
