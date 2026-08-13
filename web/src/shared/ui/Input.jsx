export default function Input({ className = '', ...props }) {
  return (
    <input
      className={`w-full border-0 border-b border-card-border bg-transparent px-0 py-2 text-sm text-ink focus:border-ink focus:outline-none ${className}`}
      {...props}
    />
  );
}
