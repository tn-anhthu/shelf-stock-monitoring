import { useEffect, useState } from 'react';
import UploadStep from '../features/scan-wizard/UploadStep.jsx';
import CropStep from '../features/scan-wizard/CropStep.jsx';
import EditStep from '../features/scan-wizard/EditStep.jsx';
import ConfirmStep from '../features/scan-wizard/ConfirmStep.jsx';
import StepIndicator from '../features/scan-wizard/StepIndicator.jsx';
import { analyzeImage, confirmScan, fetchCatalog } from '../features/scan-wizard/api.js';
import { computeTotalValue } from '../features/scan-wizard/quantities.js';
import { useObjectUrl } from '../shared/useObjectUrl.js';

const STEPS = ['upload', 'crop', 'edit', 'confirm'];

export default function ScanPage() {
  const [step, setStep] = useState('upload');
  const [storeId, setStoreId] = useState('');
  const [shelfId, setShelfId] = useState('');
  const [originalFile, setOriginalFile] = useState(null);
  const [croppedImageBlob, setCroppedImageBlob] = useState(null);
  const [analyzeResult, setAnalyzeResult] = useState(null);
  const [quantities, setQuantities] = useState([]);
  const [catalog, setCatalog] = useState([]);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState(null);
  const [confirming, setConfirming] = useState(false);
  const [confirmError, setConfirmError] = useState(null);
  const [confirmed, setConfirmed] = useState(false);

  const croppedImageUrl = useObjectUrl(croppedImageBlob);

  useEffect(() => {
    fetchCatalog().then(setCatalog).catch(() => setCatalog([]));
  }, []);

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
      setCroppedImageBlob(croppedBlob);
      setQuantities(result.quantities.map((q) => ({ ...q })));
      setStep('edit');
    } catch (err) {
      setAnalyzeError(err.message);
    } finally {
      setAnalyzing(false);
    }
  }

  async function handleConfirm() {
    setConfirming(true);
    setConfirmError(null);
    try {
      await confirmScan({
        scan_id: analyzeResult.scan_id,
        store_id: storeId,
        shelf_id: shelfId,
        quantities,
        total_value: computeTotalValue(quantities),
      });
      setConfirmed(true);
    } catch (err) {
      setConfirmError(err.message);
    } finally {
      setConfirming(false);
    }
  }

  function handleReset() {
    setStep('upload');
    setStoreId('');
    setShelfId('');
    setOriginalFile(null);
    setCroppedImageBlob(null);
    setAnalyzeResult(null);
    setQuantities([]);
    setAnalyzeError(null);
    setConfirmError(null);
    setConfirmed(false);
  }

  return (
    <div className="mx-auto max-w-6xl">
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
        <EditStep
          quantities={quantities}
          setQuantities={setQuantities}
          catalog={catalog}
          boxes={analyzeResult?.boxes ?? []}
          imageUrl={croppedImageUrl}
          imageWidth={analyzeResult?.image?.width ?? 0}
          imageHeight={analyzeResult?.image?.height ?? 0}
          onNext={() => setStep('confirm')}
        />
      )}
      {step === 'confirm' && (
        <ConfirmStep
          storeId={storeId}
          shelfId={shelfId}
          quantities={quantities}
          confirming={confirming}
          confirmError={confirmError}
          confirmed={confirmed}
          onConfirm={handleConfirm}
          onReset={handleReset}
        />
      )}
    </div>
  );
}
