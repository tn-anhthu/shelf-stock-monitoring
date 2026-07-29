import { useState } from 'react';
import UploadStep from '../features/scan-wizard/UploadStep.jsx';
import StepIndicator from '../features/scan-wizard/StepIndicator.jsx';

const STEPS = ['upload', 'crop', 'edit', 'confirm'];

export default function ScanPage() {
  const [step, setStep] = useState('upload');
  const [storeId, setStoreId] = useState('');
  const [shelfId, setShelfId] = useState('');
  const [originalFile, setOriginalFile] = useState(null);

  function handleUploadNext({ storeId, shelfId, file }) {
    setStoreId(storeId);
    setShelfId(shelfId);
    setOriginalFile(file);
    setStep('crop');
  }

  return (
    <div className="mx-auto max-w-3xl">
      <StepIndicator steps={STEPS} current={step} />
      {step === 'upload' && <UploadStep onNext={handleUploadNext} />}
      {step === 'crop' && <p className="text-slate-500">Bước Crop — đang xây dựng.</p>}
      {step === 'edit' && <p className="text-slate-500">Bước Edit — đang xây dựng.</p>}
      {step === 'confirm' && <p className="text-slate-500">Bước Confirm — đang xây dựng.</p>}
    </div>
  );
}
