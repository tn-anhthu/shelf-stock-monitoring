const VARIANTS = {
  primary: 'bg-ink text-page hover:bg-text-secondary disabled:opacity-50',
  outline: 'bg-transparent text-ink border border-ink hover:bg-page disabled:opacity-50',
};

export default function Button({ variant = 'primary', className = '', ...props }) {
  return (
    <button
      className={`rounded-sm px-4 py-2 text-sm font-medium transition ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  );
}
