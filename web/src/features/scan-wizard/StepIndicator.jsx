const LABELS = {
  upload: 'Upload',
  crop: 'Crop',
  edit: 'Edit',
  confirm: 'Confirm',
};

export default function StepIndicator({ steps, current }) {
  const currentIndex = steps.indexOf(current);
  return (
    <ol className="mb-6 flex items-start">
      {steps.map((step, index) => {
        const isDone = index < currentIndex;
        const isCurrent = index === currentIndex;
        return (
          <li key={step} className="flex flex-1 items-center">
            <div className="flex flex-col items-center gap-1">
              <div
                className={`flex h-7 w-7 items-center justify-center rounded-full font-heading text-xs font-semibold ${
                  isDone || isCurrent ? 'bg-ink text-white' : 'bg-page text-text-muted'
                }`}
              >
                {isDone ? '✓' : index + 1}
              </div>
              <span className={`text-xs ${isCurrent ? 'font-medium text-ink' : 'text-text-muted'}`}>
                {LABELS[step]}
              </span>
            </div>
            {index < steps.length - 1 && (
              <div className={`mx-2 mb-4 h-0.5 flex-1 ${isDone ? 'bg-ink' : 'bg-card-border'}`} />
            )}
          </li>
        );
      })}
    </ol>
  );
}
