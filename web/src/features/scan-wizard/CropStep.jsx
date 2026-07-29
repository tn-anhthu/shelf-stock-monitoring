import { useEffect, useRef, useState } from 'react';
import { Cropper } from 'react-cropper';
import 'cropperjs/dist/cropper.css';

export default function CropStep({ originalFile, analyzing, analyzeError, onAnalyze }) {
  const cropperRef = useRef(null);
  const [imageUrl] = useState(() => URL.createObjectURL(originalFile));

  useEffect(() => {
    return () => URL.revokeObjectURL(imageUrl);
  }, [imageUrl]);

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
      <h2 className="text-lg font-semibold">2. Chỉnh vùng kệ hàng</h2>
      {analyzeError && <p className="rounded bg-red-50 px-3 py-2 text-red-700">{analyzeError}</p>}
      <Cropper
        src={imageUrl}
        style={{ height: 420, width: '100%' }}
        autoCropArea={0.9}
        viewMode={1}
        guides
        ref={cropperRef}
      />
      <button
        type="button"
        onClick={handleAnalyzeClick}
        disabled={analyzing}
        className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-50"
      >
        {analyzing ? 'Đang phân tích…' : 'Phân tích'}
      </button>
    </div>
  );
}
