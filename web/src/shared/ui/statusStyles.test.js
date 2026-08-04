import { describe, expect, test } from 'vitest';
import { getStatusStyle } from './statusStyles.js';

describe('getStatusStyle', () => {
  test('maps ok to green tokens', () => {
    expect(getStatusStyle('ok')).toEqual({ bg: '#EAF3DE', text: '#173404', label: 'ok' });
  });

  test('maps low to amber tokens', () => {
    expect(getStatusStyle('low')).toEqual({ bg: '#FAEEDA', text: '#412402', label: 'low' });
  });

  test('maps out to red tokens', () => {
    expect(getStatusStyle('out')).toEqual({ bg: '#FCEBEB', text: '#501313', label: 'out' });
  });

  test('returns null for an unknown status', () => {
    expect(getStatusStyle('unknown')).toBeNull();
  });

  test('returns null for null or undefined', () => {
    expect(getStatusStyle(null)).toBeNull();
    expect(getStatusStyle(undefined)).toBeNull();
  });
});
