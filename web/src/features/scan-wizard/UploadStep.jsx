import { useRef, useState } from 'react';
import { isHeic, heicTo } from 'heic-to';
import Button from '../../shared/ui/Button.jsx';
import Input from '../../shared/ui/Input.jsx';
import { useObjectUrl } from '../../shared/useObjectUrl.js';

export default function UploadStep({ onNext }) {
  const [storeId, setStoreId] = useState('');
  const [shelfId, setShelfId] = useState('');
  const [file, setFile] = useState(null);
  const [converting, setConverting] = useState(false);
  const [convertError, setConvertError] = useState(null);
  const previewUrl = useObjectUrl(file);
  const cameraInputRef = useRef(null);
  const galleryInputRef = useRef(null);

  const canSubmit = storeId.trim() && shelfId.trim() && file && !converting;

  async function handleFileChange(event) {
    const picked = event.target.files?.[0] ?? null;
    if (!picked) {
      setFile(null);
      return;
    }
    setConvertError(null);
    if (await isHeic(picked)) {
      setConverting(true);
      try {
        const jpegBlob = await heicTo({ blob: picked, type: 'image/jpeg', quality: 0.92 });
        const convertedName = picked.name.replace(/\.(heic|heif)$/i, '.jpg');
        setFile(new File([jpegBlob], convertedName, { type: 'image/jpeg' }));
      } catch (err) {
        setConvertError('Không đọc được ảnh HEIC này. Thử chọn ảnh khác hoặc chuyển sang JPG/PNG.');
        setFile(null);
      } finally {
        setConverting(false);
      }
      return;
    }
    setFile(picked);
  }

  function handleSubmit(event) {
    event.preventDefault();
    if (!canSubmit) return;
    onNext({ storeId: storeId.trim(), shelfId: shelfId.trim(), file });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <h2 className="font-heading text-lg font-semibold text-ink">1. Chọn ảnh kệ hàng</h2>

      <label className="block">
        <span className="text-sm font-medium text-ink">Store ID</span>
        <Input
          type="text"
          value={storeId}
          onChange={(e) => setStoreId(e.target.value)}
          required
          className="mt-1"
        />
      </label>

      <label className="block">
        <span className="text-sm font-medium text-ink">Shelf ID</span>
        <Input
          type="text"
          value={shelfId}
          onChange={(e) => setShelfId(e.target.value)}
          required
          className="mt-1"
        />
      </label>

      <div>
        <span className="text-sm font-medium text-ink">Ảnh kệ hàng</span>

        {convertError && (
          <p className="mt-2 rounded-lg bg-status-out-bg px-3 py-2 text-sm text-status-out-text">{convertError}</p>
        )}

        {converting ? (
          <div className="mt-2 flex h-32 items-center justify-center rounded-xl border border-dashed border-card-border text-sm text-text-muted">
            Đang xử lý ảnh HEIC...
          </div>
        ) : previewUrl ? (
          <img
            src={previewUrl}
            alt="Ảnh kệ hàng đã chọn"
            className="mt-2 h-48 w-full rounded-xl border border-card-border object-cover"
          />
        ) : (
          <div className="mt-2 flex h-32 items-center justify-center rounded-xl border border-dashed border-card-border text-sm text-text-muted">
            Chưa có ảnh
          </div>
        )}

        <input
          ref={cameraInputRef}
          type="file"
          accept="image/*,.heic,.heif"
          capture="environment"
          onChange={handleFileChange}
          className="hidden"
        />
        <input
          ref={galleryInputRef}
          type="file"
          accept="image/*,.heic,.heif"
          onChange={handleFileChange}
          className="hidden"
        />

        <div className="mt-2 flex gap-2">
          <Button type="button" variant="outline" className="flex-1" onClick={() => cameraInputRef.current?.click()}>
            Chụp ảnh
          </Button>
          <Button type="button" variant="outline" className="flex-1" onClick={() => galleryInputRef.current?.click()}>
            Thư viện
          </Button>
        </div>
      </div>

      <Button type="submit" disabled={!canSubmit} className="w-full">
        Tiếp tục
      </Button>
    </form>
  );
}
