const VARIANTS = {
  primary: 'bg-ink text-white hover:bg-neutral-800 disabled:opacity-50',
  outline: 'bg-white text-ink border border-ink hover:bg-slate-50 disabled:opacity-50',
};

export default function Button({ variant = 'primary', className = '', ...props }) {
  return (
    <button
      className={`rounded-lg px-4 py-2 text-sm font-medium transition ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  );
}
