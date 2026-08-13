import Button from '../../shared/ui/Button.jsx';

export default function ErrorBanner({ message, onRetry }) {
  return (
    <div className="flex flex-col items-start gap-3 border border-dashed border-status-out py-6 text-center sm:flex-row sm:items-center sm:justify-between sm:px-4 sm:text-left">
      <p className="text-sm text-status-out">Không tải được dữ liệu kệ hàng{message ? `: ${message}` : '.'}</p>
      <Button type="button" variant="outline" onClick={onRetry}>
        Thử lại
      </Button>
    </div>
  );
}
