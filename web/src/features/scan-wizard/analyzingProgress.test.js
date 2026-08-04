import { describe, expect, test } from 'vitest';
import {
  ANALYZING_STEP_LABELS,
  formatElapsed,
  getAnalyzingCurrentStepText,
  getAnalyzingSecondaryMessage,
  getAnalyzingStepStatuses,
} from './analyzingProgress.js';

describe('ANALYZING_STEP_LABELS', () => {
  test('has the 5 fixed step labels in order', () => {
    expect(ANALYZING_STEP_LABELS).toEqual([
      'Tải ảnh lên',
      'Phát hiện sản phẩm trên kệ',
      'Nhận diện từng SKU',
      'Xác minh với AI',
      'Tổng hợp kết quả',
    ]);
  });
});

describe('getAnalyzingStepStatuses', () => {
  test('step 1 is current at the start', () => {
    expect(getAnalyzingStepStatuses(0)).toEqual(['current', 'pending', 'pending', 'pending', 'pending']);
  });

  test('step 1 stays current right up to its boundary', () => {
    expect(getAnalyzingStepStatuses(1499)).toEqual(['current', 'pending', 'pending', 'pending', 'pending']);
  });

  test('step 2 becomes current at 1.5s', () => {
    expect(getAnalyzingStepStatuses(1500)).toEqual(['done', 'current', 'pending', 'pending', 'pending']);
  });

  test('step 2 stays current right up to its boundary', () => {
    expect(getAnalyzingStepStatuses(3999)).toEqual(['done', 'current', 'pending', 'pending', 'pending']);
  });

  test('step 3 becomes current at 4s', () => {
    expect(getAnalyzingStepStatuses(4000)).toEqual(['done', 'done', 'current', 'pending', 'pending']);
  });

  test('step 3 stays current right up to its boundary', () => {
    expect(getAnalyzingStepStatuses(6999)).toEqual(['done', 'done', 'current', 'pending', 'pending']);
  });

  test('step 4 becomes current at 7s', () => {
    expect(getAnalyzingStepStatuses(7000)).toEqual(['done', 'done', 'done', 'current', 'pending']);
  });

  test('step 4 stays current indefinitely (step 5 is never simulated)', () => {
    expect(getAnalyzingStepStatuses(15 * 60 * 1000)).toEqual(['done', 'done', 'done', 'current', 'pending']);
  });
});

describe('getAnalyzingCurrentStepText', () => {
  test('reads "Đang tải ảnh lên…" during step 1', () => {
    expect(getAnalyzingCurrentStepText(0)).toBe('Đang tải ảnh lên…');
  });

  test('reads "Đang phát hiện sản phẩm trên kệ…" during step 2', () => {
    expect(getAnalyzingCurrentStepText(1500)).toBe('Đang phát hiện sản phẩm trên kệ…');
  });

  test('reads "Đang nhận diện từng SKU…" during step 3', () => {
    expect(getAnalyzingCurrentStepText(4000)).toBe('Đang nhận diện từng SKU…');
  });

  test('reads "Đang xác minh với AI…" during step 4', () => {
    expect(getAnalyzingCurrentStepText(7000)).toBe('Đang xác minh với AI…');
  });

  test('stays on step 4\'s text no matter how long the wait', () => {
    expect(getAnalyzingCurrentStepText(20 * 60 * 1000)).toBe('Đang xác minh với AI…');
  });
});

describe('getAnalyzingSecondaryMessage', () => {
  test('is null before 20s', () => {
    expect(getAnalyzingSecondaryMessage(0)).toBeNull();
    expect(getAnalyzingSecondaryMessage(19999)).toBeNull();
  });

  test('switches to the slow-scan notice at exactly 20s', () => {
    expect(getAnalyzingSecondaryMessage(20000)).toBe(
      'Ảnh nhiều sản phẩm có thể mất vài phút, hệ thống vẫn đang xử lý',
    );
  });

  test('stays on the slow-scan notice well past 20s', () => {
    expect(getAnalyzingSecondaryMessage(10 * 60 * 1000)).toBe(
      'Ảnh nhiều sản phẩm có thể mất vài phút, hệ thống vẫn đang xử lý',
    );
  });
});

describe('formatElapsed', () => {
  test('formats 0ms as 0:00', () => {
    expect(formatElapsed(0)).toBe('0:00');
  });

  test('formats sub-minute durations as 0:SS', () => {
    expect(formatElapsed(7000)).toBe('0:07');
    expect(formatElapsed(59000)).toBe('0:59');
  });

  test('rolls over into minutes', () => {
    expect(formatElapsed(60000)).toBe('1:00');
    expect(formatElapsed(125000)).toBe('2:05');
  });

  test('truncates partial seconds rather than rounding', () => {
    expect(formatElapsed(7999)).toBe('0:07');
  });
});
