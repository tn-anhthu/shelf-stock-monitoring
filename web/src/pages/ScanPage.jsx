import { useEffect, useState } from 'react';
import UploadStep from '../features/scan-wizard/UploadStep.jsx';
import CropStep from '../features/scan-wizard/CropStep.jsx';
import EditStep from '../features/scan-wizard/EditStep.jsx';
import ConfirmStep from '../features/scan-wizard/ConfirmStep.jsx';
import StepIndicator from '../features/scan-wizard/StepIndicator.jsx';
import { analyzeImage, confirmScan, uploadScanImage, fetchCatalog } from '../features/scan-wizard/api.js';
import { computeTotalValue } from '../features/scan-wizard/quantities.js';
import { useObjectUrl } from '../shared/useObjectUrl.js';

const STEPS = ['upload', 'crop', 'edit', 'confirm'];

export default function ScanPage({ prefill }) {
  const [step, setStep] = useState('upload');
  const [category, setCategory] = useState(prefill?.category ?? null);
  const [container, setContainer] = useState(prefill?.container ?? null);
  const [categoryName, setCategoryName] = useState(null);
  const [containerLabel, setContainerLabel] = useState(null);
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

  // TEMP DEV MOCK — remove before shipping. ?mock=edit jumps straight to the
  // Edit step with fake detection data so the UI can be checked without a
  // live ml-service run.
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get('mock') !== 'edit') return;
    const mockQuantities = [
      { sku_id: 'choco_pie_org', sku_name: 'Bánh chocopie Orion hộp 217.8g (6 cái)', facing_count: 4, depth: 2, total_quantity: 8, shelf_full_qty: 10, unit_price: 30000, subtotal: 240000, flag_status: 'ok' },
      { sku_id: 'choco_pie_dark', sku_name: 'Bánh chocopie Orion Dark vị ca cao hộp 180g (6 cái)', facing_count: 2, depth: 2, total_quantity: 4, shelf_full_qty: 10, unit_price: 34000, subtotal: 136000, flag_status: 'low' },
      { sku_id: 'karo_org', sku_name: 'Bánh trứng tươi chà bông Karo Richy túi 156g', facing_count: 0, depth: 1, total_quantity: 0, shelf_full_qty: 10, unit_price: 41000, subtotal: 0, flag_status: 'out' },
      { sku_id: 'karo_phomai', sku_name: 'Bánh trứng tươi phô mai hoàng kim Karo Richy túi 156g', facing_count: 3, depth: 1, total_quantity: 3, shelf_full_qty: 10, unit_price: 41000, subtotal: 123000, flag_status: null },
    ];
    const mockBoxes = [
      { box_id: 'b1', bbox: [230, 350, 900, 900], type: 'product', sku_id: 'choco_pie_org', confidence: 0.94, is_unknown: false, excluded_from_count: false, needs_review: false },
      { box_id: 'b2', bbox: [950, 350, 1600, 900], type: 'product', sku_id: 'choco_pie_dark', confidence: 0.88, is_unknown: false, excluded_from_count: false, needs_review: false },
      { box_id: 'b3', bbox: [1650, 350, 2300, 900], type: 'gap', sku_id: 'karo_org', confidence: 0.5, is_unknown: false, excluded_from_count: true, needs_review: false },
      { box_id: 'b4', bbox: [230, 950, 900, 1500], type: 'product', sku_id: 'karo_phomai', confidence: 0.62, is_unknown: false, excluded_from_count: false, needs_review: false },
      { box_id: 'b5', bbox: [950, 950, 1600, 1500], type: 'product', sku_id: null, confidence: 0.4, is_unknown: true, excluded_from_count: false, needs_review: false },
      { box_id: 'b6', bbox: [1650, 950, 2300, 1500], type: 'product', sku_id: null, confidence: 0.3, is_unknown: false, excluded_from_count: true, needs_review: true },
    ];
    setCatalog((prev) => (prev.length ? prev : [
      { sku_id: 'choco_pie_org', name: 'Bánh chocopie Orion hộp 217.8g (6 cái)', price: 30000, shelf_full_qty: 10 },
      { sku_id: 'choco_pie_dark', name: 'Bánh chocopie Orion Dark vị ca cao hộp 180g (6 cái)', price: 34000, shelf_full_qty: 10 },
      { sku_id: 'karo_org', name: 'Bánh trứng tươi chà bông Karo Richy túi 156g', price: 41000, shelf_full_qty: 10 },
      { sku_id: 'karo_phomai', name: 'Bánh trứng tươi phô mai hoàng kim Karo Richy túi 156g', price: 41000, shelf_full_qty: 10 },
    ]));
    setAnalyzeResult({ scan_id: 'mock', boxes: mockBoxes, quantities: mockQuantities, image: { width: 4032, height: 3024 } });
    fetch('/mock-shelf.jpg').then((r) => r.blob()).then(setCroppedImageBlob);
    setQuantities(mockQuantities);
    setCategory('demo-category');
    setContainer('demo-container');
    setCategoryName('Danh mục demo');
    setContainerLabel('Kệ demo');
    setStep('edit');
  }, []);

  function handleUploadNext({ category, container, categoryName, containerLabel, file }) {
    setCategory(category);
    setContainer(container);
    setCategoryName(categoryName);
    setContainerLabel(containerLabel);
    setOriginalFile(file);
    setAnalyzeError(null);
    setStep('crop');
  }

  async function handleCropAnalyze(croppedBlob) {
    setAnalyzing(true);
    setAnalyzeError(null);
    try {
      const result = await analyzeImage({
        category,
        container,
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
        category,
        container,
        quantities,
        total_value: computeTotalValue(quantities),
        boxes: analyzeResult.boxes,
      });
      if (croppedImageBlob && analyzeResult.image) {
        // Fail-open: lỗi upload ảnh không được chặn xác nhận scan đã thành công.
        uploadScanImage({
          scanId: analyzeResult.scan_id,
          imageBlob: croppedImageBlob,
          width: analyzeResult.image.width,
          height: analyzeResult.image.height,
        }).catch(() => {});
      }
      setConfirmed(true);
    } catch (err) {
      setConfirmError(err.message);
    } finally {
      setConfirming(false);
    }
  }

  function handleReset() {
    setStep('upload');
    setCategory(null);
    setContainer(null);
    setCategoryName(null);
    setContainerLabel(null);
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
      {step === 'upload' && (
        <UploadStep onNext={handleUploadNext} initialCategory={prefill?.category} initialContainer={prefill?.container} />
      )}
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
          categoryName={categoryName}
          containerLabel={containerLabel}
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
