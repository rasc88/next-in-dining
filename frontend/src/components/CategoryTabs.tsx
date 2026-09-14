export function CategoryTabs({
  categories,
  active,
  onSelect,
}: {
  categories: string[];
  active: string;
  onSelect: (category: string) => void;
}) {
  return (
    <div className="category-tabs" role="tablist" aria-label="Filter by seating category">
      {['All', ...categories].map((category) => (
        <button
          key={category}
          type="button"
          role="tab"
          aria-selected={active === category}
          className={`category-tab${active === category ? ' active' : ''}`}
          onClick={() => onSelect(category)}
        >
          {category}
        </button>
      ))}
    </div>
  );
}
