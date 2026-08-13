import { IconLock } from '../../shared/ui/icons.jsx';

export default function CategoryContainerPicker({ categories, category, container, onCategoryChange, onContainerChange }) {
  const selected = categories.find((c) => c.slug === category);

  return (
    <div className="flex flex-col gap-3 border-b border-card-border pb-4 sm:flex-row sm:items-end sm:gap-9">
      <div className="relative w-full sm:w-56">
        <select
          value={category}
          onChange={(e) => onCategoryChange(e.target.value)}
          className="w-full appearance-none border-0 border-b-2 border-ink bg-transparent py-1.5 pr-6 font-heading text-sm font-semibold text-ink focus:outline-none"
        >
          {categories.map((c) => (
            <option key={c.slug} value={c.slug} disabled={!c.active}>
              {c.name}
              {!c.active ? ' (khoá)' : ''}
            </option>
          ))}
        </select>
        <span className="pointer-events-none absolute right-1 top-1/2 -translate-y-1/2 text-xs text-text-secondary">▾</span>
      </div>

      <div className="flex gap-4 text-sm">
        {selected?.containers.map((cont) => {
          const isActive = container === cont.id;
          return (
            <button
              key={cont.id}
              type="button"
              disabled={!cont.active}
              onClick={() => onContainerChange(cont.id)}
              className={
                isActive
                  ? 'flex items-center gap-1 border-b-2 border-ink pb-1.5 font-semibold text-ink'
                  : cont.active
                    ? 'flex items-center gap-1 border-b-2 border-transparent pb-1.5 text-text-secondary hover:text-ink'
                    : 'flex cursor-not-allowed items-center gap-1 border-b-2 border-transparent pb-1.5 text-text-muted'
              }
            >
              {cont.label}
              {!cont.active && <IconLock />}
            </button>
          );
        })}
      </div>
    </div>
  );
}
