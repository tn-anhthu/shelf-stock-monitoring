import Button from '../../shared/ui/Button.jsx';

export default function EmptyState({ onScanNow }) {
  return (
    <div className="flex flex-col items-center gap-3 border border-dashed border-card-border py-16 text-center">
      <p className="text-sm text-text-secondary">Kệ này chưa có lần scan nào.</p>
      <Button type="button" onClick={onScanNow}>
        Scan ngay
      </Button>
    </div>
  );
}
