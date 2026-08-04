// Client-side simulated progress for the analyzing modal. /predict is a
// single synchronous call with no real progress signal from the backend, so
// steps 1-3 are timed guesses; step 4 ("Xác minh với AI") is where the real
// work (Gemini verification per detected box) happens and can legitimately
// take minutes on a slow network (see memory: gemini-api-can-be-severely-slow),
// so it holds indefinitely instead of being timed. Step 5 is never simulated
// — the modal unmounts as soon as the real response resolves.
export const ANALYZING_STEP_LABELS = [
  'Tải ảnh lên',
  'Phát hiện sản phẩm trên kệ',
  'Nhận diện từng SKU',
  'Xác minh với AI',
  'Tổng hợp kết quả',
];

const STEP_BOUNDARIES_MS = [1500, 4000, 7000];
const STALL_WARNING_AT_MS = 20000;
const STALL_WARNING_MESSAGE = 'Ảnh nhiều sản phẩm có thể mất vài phút, hệ thống vẫn đang xử lý';

function getAnalyzingCurrentStepIndex(elapsedMs) {
  for (let i = 0; i < STEP_BOUNDARIES_MS.length; i++) {
    if (elapsedMs < STEP_BOUNDARIES_MS[i]) return i;
  }
  return STEP_BOUNDARIES_MS.length;
}

export function getAnalyzingStepStatuses(elapsedMs) {
  const currentIndex = getAnalyzingCurrentStepIndex(elapsedMs);
  return ANALYZING_STEP_LABELS.map((_, index) => {
    if (index < currentIndex) return 'done';
    if (index === currentIndex) return 'current';
    return 'pending';
  });
}

export function getAnalyzingCurrentStepText(elapsedMs) {
  const label = ANALYZING_STEP_LABELS[getAnalyzingCurrentStepIndex(elapsedMs)];
  return `Đang ${label.charAt(0).toLowerCase()}${label.slice(1)}…`;
}

export function getAnalyzingSecondaryMessage(elapsedMs) {
  return elapsedMs >= STALL_WARNING_AT_MS ? STALL_WARNING_MESSAGE : null;
}

export function formatElapsed(elapsedMs) {
  const totalSeconds = Math.floor(elapsedMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}
