const STATUS_STYLES = {
  ok: { bg: '#EAF3DE', text: '#173404', label: 'ok' },
  low: { bg: '#FAEEDA', text: '#412402', label: 'low' },
  out: { bg: '#FCEBEB', text: '#501313', label: 'out' },
};

export function getStatusStyle(flagStatus) {
  return STATUS_STYLES[flagStatus] ?? null;
}
