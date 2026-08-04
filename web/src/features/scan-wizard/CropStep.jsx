import { useRef } from 'react';
import { Cropper } from 'react-cropper';
import 'cropperjs/dist/cropper.css';
import Button from '../../shared/ui/Button.jsx';
import { useObjectUrl } from '../../shared/useObjectUrl.js';
import AnalyzingModal from './AnalyzingModal.jsx';

const CORNER_BASE = 'pointer-events-none absolute h-6 w-6 border-ink';

export default function CropStep({ originalFile, analyzing, analyzeError, onAnalyze }) {
  const cropperRef = useRef(null);
  const imageUrl = useObjectUrl(originalFile);

  function handleAnalyzeClick() {
    const cropper = cropperRef.current?.cropper;
    if (!cropper) return;
    const canvas = cropper.getCroppedCanvas();
    canvas.toBlob(
      (blob) => {
        if (blob) onAnalyze(blob);
      },
      'image/jpeg',
      0.92,
    );
  }

  return (
    <div className="space-y-4">
      <h2 className="font-heading text-lg font-semibold text-ink">2. Chỉnh vùng kệ hàng</h2>

      {analyzeError && (
        <p className="rounded-lg bg-status-out-bg px-3 py-2 text-sm text-status-out-text">{analyzeError}</p>
      )}

      <div className="relative">
        {imageUrl && (
          <Cropper
            src={imageUrl}
            style={{ height: 420, width: '100%' }}
            autoCropArea={0.9}
            viewMode={1}
            guides
            ref={cropperRef}
          />
        )}
        <span className={`${CORNER_BASE} left-2 top-2 border-l-2 border-t-2`} />
        <span className={`${CORNER_BASE} right-2 top-2 border-r-2 border-t-2`} />
        <span className={`${CORNER_BASE} bottom-2 left-2 border-b-2 border-l-2`} />
        <span className={`${CORNER_BASE} bottom-2 right-2 border-b-2 border-r-2`} />
      </div>

      <Button type="button" onClick={handleAnalyzeClick} disabled={analyzing}>
        Phân tích
      </Button>

      <AnalyzingModal open={analyzing} />
    </div>
  );
}
