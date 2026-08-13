// Category/container registry for the Inventory page -- docs/superpowers/specs/2026-08-10-dashboard-design.md §2-3.
// The `scans` table columns are named category/container directly (no longer
// a store_id/shelf_id reuse) -- see docs/superpowers/specs/2026-08-13-category-container-naming-design.md.

const CATEGORIES = [
  {
    slug: 'mi-goi',
    name: 'Mì gói',
    catalogGroup: 'Mì/cháo/phở ăn liền',
    active: true,
    containerType: 'Kệ',
    containers: [
      { id: 'ke-a', label: 'Kệ A', active: true },
      { id: 'ke-b', label: 'Kệ B', active: false },
      { id: 'ke-c', label: 'Kệ C', active: false },
    ],
  },
  {
    slug: 'sua',
    name: 'Sữa',
    catalogGroup: 'Sữa & sản phẩm từ sữa',
    active: true,
    containerType: 'Kệ',
    containers: [
      { id: 'ke-a', label: 'Kệ A', active: true },
      { id: 'ke-b', label: 'Kệ B', active: false },
      { id: 'ke-c', label: 'Kệ C', active: false },
    ],
  },
  {
    slug: 'nuoc-giai-khat',
    name: 'Nước giải khát',
    catalogGroup: 'Nước giải khát có ga',
    active: true,
    containerType: 'Tủ',
    containers: [
      { id: 'tu-a', label: 'Tủ A', active: true },
      { id: 'tu-b', label: 'Tủ B', active: false },
      { id: 'tu-c', label: 'Tủ C', active: false },
    ],
  },
  {
    slug: 'banh-keo',
    name: 'Bánh kẹo',
    catalogGroup: 'Bánh kẹo',
    active: false,
    containerType: 'Kệ',
    containers: [],
  },
  {
    slug: 'cham-soc-nha-cua',
    name: 'Chăm sóc nhà cửa',
    catalogGroup: 'Chăm sóc nhà cửa',
    active: false,
    containerType: 'Kệ',
    containers: [],
  },
  {
    slug: 'nuoc-uong-khong-ga',
    name: 'Nước uống không ga / nước suối',
    catalogGroup: 'Nước uống không ga / nước suối',
    active: false,
    containerType: 'Tủ',
    containers: [],
  },
  {
    slug: 'snack',
    name: 'Snack/đồ ăn vặt',
    catalogGroup: 'Snack/đồ ăn vặt',
    active: false,
    containerType: 'Kệ',
    containers: [],
  },
];

function findCategory(categorySlug) {
  return CATEGORIES.find((c) => c.slug === categorySlug);
}

function findContainer(categorySlug, containerId) {
  const category = findCategory(categorySlug);
  return category?.containers.find((c) => c.id === containerId);
}

function isActiveShelf(categorySlug, containerId) {
  const category = findCategory(categorySlug);
  const container = findContainer(categorySlug, containerId);
  return Boolean(category?.active && container?.active);
}

module.exports = { CATEGORIES, findCategory, findContainer, isActiveShelf };
