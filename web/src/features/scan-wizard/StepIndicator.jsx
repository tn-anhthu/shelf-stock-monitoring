const LABELS = {
  upload: 'Upload',
  crop: 'Crop',
  edit: 'Edit',
  confirm: 'Confirm',
};

export default function StepIndicator({ steps, current }) {
  const currentIndex = steps.indexOf(current);
  return (
    <ol className="mb-6 flex gap-2 text-sm">
      {steps.map((step, index) => (
        <li
          key={step}
          className={`flex-1 rounded-lg px-3 py-2 text-center font-heading font-medium ${
            index <= currentIndex ? 'bg-ink text-white' : 'bg-page text-text-muted'
          }`}
        >
          {index + 1}. {LABELS[step]}
        </li>
      ))}
    </ol>
  );
}
