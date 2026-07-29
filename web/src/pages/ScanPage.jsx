import { useState } from 'react';
import UploadStep from '../features/scan-wizard/UploadStep.jsx';
import CropStep from '../features/scan-wizard/CropStep.jsx';
import StepIndicator from '../features/scan-wizard/StepIndicator.jsx';
import { analyzeImage } from '../features/scan-wizard/api.js';

const STEPS = ['upload', 'crop', 'edit', 'confirm'];

export default function ScanPage() {
  const [step, setStep] = useState('upload');
  const [storeId, setStoreId] = useState('');
  const [shelfId, setShelfId] = useState('');
  const [originalFile, setOriginalFile] = useState(null);
  const [analyzeResult, setAnalyzeResult] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState(null);

  function handleUploadNext({ storeId, shelfId, file }) {
    setStoreId(storeId);
    setShelfId(shelfId);
    setOriginalFile(file);
    setAnalyzeError(null);
    setStep('crop');
  }

  async function handleCropAnalyze(croppedBlob) {
    setAnalyzing(true);
    setAnalyzeError(null);
    try {
      const result = await analyzeImage({
        storeId,
        shelfId,
        imageBlob: croppedBlob,
        filename: originalFile?.name ?? 'shelf.jpg',
      });
      if (result.status === 'failed') {
        setAnalyzeError(result.error_message || 'Phân tích ảnh thất bại.');
        return;
      }
      setAnalyzeResult(result);
      setStep('edit');
    } catch (err) {
      setAnalyzeError(err.message);
    } finally {
      setAnalyzing(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <StepIndicator steps={STEPS} current={step} />
      {step === 'upload' && <UploadStep onNext={handleUploadNext} />}
      {step === 'crop' && originalFile && (
        <CropStep
          originalFile={originalFile}
          analyzing={analyzing}
          analyzeError={analyzeError}
          onAnalyze={handleCropAnalyze}
        />
      )}
      {step === 'edit' && (
        <div className="space-y-2 text-slate-500">
          <p>Bước Edit — đang xây dựng.</p>
          <pre className="overflow-auto rounded bg-slate-100 p-3 text-xs">
            {JSON.stringify(analyzeResult?.quantities, null, 2)}
          </pre>
        </div>
      )}
      {step === 'confirm' && <p className="text-slate-500">Bước Confirm — đang xây dựng.</p>}
    </div>
  );
}
