export default function Input({ className = '', ...props }) {
  return (
    <input
      className={`w-full rounded-lg border border-card-border px-3 py-2 text-sm focus:border-ink focus:outline-none ${className}`}
      {...props}
    />
  );
}
