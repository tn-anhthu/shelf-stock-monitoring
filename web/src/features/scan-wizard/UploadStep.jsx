import { useEffect, useRef, useState } from 'react';
import { isHeic, heicTo } from 'heic-to';
import Button from '../../shared/ui/Button.jsx';
import { IconClose } from '../../shared/ui/icons.jsx';
import { useObjectUrl } from '../../shared/useObjectUrl.js';
import { fetchShelves } from './api.js';
import CategoryContainerPicker from '../inventory/CategoryContainerPicker.jsx';

export default function UploadStep({ onNext, initialCategory = null, initialContainer = null }) {
  const [categories, setCategories] = useState(null);
  const [category, setCategory] = useState(initialCategory);
  const [container, setContainer] = useState(initialContainer);
  const [file, setFile] = useState(null);
  const [converting, setConverting] = useState(false);
  const [convertError, setConvertError] = useState(null);
  const [showPhotoTips, setShowPhotoTips] = useState(false);
  const previewUrl = useObjectUrl(file);
  const cameraInputRef = useRef(null);
  const galleryInputRef = useRef(null);
  const photoTipsRef = useRef(null);

  useEffect(() => {
    fetchShelves()
      .then(({ categories: cats }) => {
        setCategories(cats);
        if (!initialCategory) {
          const firstActiveCategory = cats.find((c) => c.active);
          const firstActiveContainer = firstActiveCategory?.containers.find((c) => c.active);
          setCategory(firstActiveCategory?.slug ?? null);
          setContainer(firstActiveContainer?.id ?? null);
        }
      })
      .catch(() => setCategories([]));
  }, []);

  function handleCategoryChange(slug) {
    setCategory(slug);
    const nextCategory = categories.find((c) => c.slug === slug);
    const firstActiveContainer = nextCategory?.containers.find((c) => c.active);
    setContainer(firstActiveContainer?.id ?? null);
  }

  useEffect(() => {
    if (!showPhotoTips) return;
    function handleClickOutside(event) {
      if (photoTipsRef.current && !photoTipsRef.current.contains(event.target)) {
        setShowPhotoTips(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('touchstart', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('touchstart', handleClickOutside);
    };
  }, [showPhotoTips]);

  const canSubmit = Boolean(category) && Boolean(container) && file && !converting;

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
    onNext({ category, container, file });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <h2 className="font-heading text-lg font-semibold text-ink">1. Chọn ảnh kệ hàng</h2>

      {!categories ? (
        <p className="text-sm text-text-muted">Đang tải danh mục…</p>
      ) : (
        <CategoryContainerPicker
          categories={categories}
          category={category}
          container={container}
          onCategoryChange={handleCategoryChange}
          onContainerChange={setContainer}
        />
      )}

      <div>
        <div className="relative flex items-center gap-1.5" ref={photoTipsRef}>
          <span className="text-sm font-medium text-ink">Ảnh kệ hàng</span>
          <button
            type="button"
            aria-label="Mẹo chụp ảnh kệ hàng"
            aria-expanded={showPhotoTips}
            onClick={() => setShowPhotoTips((prev) => !prev)}
            className="flex h-5 w-5 items-center justify-center rounded-full border border-card-border text-xs leading-none text-text-secondary hover:border-border-strong hover:text-ink"
          >
            ?
          </button>

          {showPhotoTips && (
            <div className="absolute left-0 top-full z-10 mt-2 w-72 max-w-[90vw] rounded-sm border border-card-border bg-page p-3 text-sm shadow-lg">
              <div className="mb-1.5 flex items-start justify-between gap-2">
                <p className="font-medium text-ink">
                  Mẹo chụp ảnh kệ hàng để hệ thống đọc chính xác hơn:
                </p>
                <button
                  type="button"
                  aria-label="Đóng"
                  onClick={() => setShowPhotoTips(false)}
                  className="shrink-0 text-text-secondary hover:text-ink"
                >
                  <IconClose />
                </button>
              </div>
              <ul className="list-disc space-y-1 pl-4 text-text-secondary">
                <li>Đứng cách kệ ~1-1.5m, giữ điện thoại song song mặt kệ (không xoay nghiêng)</li>
                <li>
                  Với tủ lạnh/tủ mát: tránh để khung tủ, viền kim loại, hoặc banner khuyến mãi lọt vào khung
                  hình. Chỉ chụp phần sản phẩm trên kệ
                </li>
                <li>Đủ ánh sáng, tránh chói/phản chiếu trên bao bì bóng</li>
                <li>Chụp thẳng theo phương ngang của kệ, không chụp xéo từ dưới lên hoặc trên xuống</li>
              </ul>
            </div>
          )}
        </div>

        {convertError && <p className="mt-2 text-sm text-status-out">{convertError}</p>}

        {converting ? (
          <div className="mt-2 flex h-80 items-center justify-center border border-dashed border-card-border text-sm text-text-secondary">
            Đang xử lý ảnh HEIC...
          </div>
        ) : previewUrl ? (
          <img
            src={previewUrl}
            alt="Ảnh kệ hàng đã chọn"
            className="mt-2 h-80 w-full border border-card-border bg-page object-contain sm:h-[28rem]"
          />
        ) : (
          <div className="mt-2 flex h-80 items-center justify-center border border-dashed border-card-border text-sm text-text-secondary">
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
