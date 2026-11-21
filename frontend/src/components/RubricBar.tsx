/**
 * RubricBar.tsx — one horizontal bar split into coloured segments, one per
 * scoring criterion, each as wide as its weight. It lets you SEE what a role
 * values. Used on the dashboard, the role page and the "new role" form.
 *
 * `compact` hides the legend (used inside list rows).
 */
import type { Criterion } from "@/lib/api";

// Segment colours, reused in order.
export const RUBRIC_COLORS = ["#2f4bff", "#7a5af8", "#0f9d93", "#e0792a", "#d6456d", "#5b9a2d"];

export function RubricBar({ criteria, compact = false }: { criteria: Pick<Criterion, "name" | "weight">[]; compact?: boolean }) {
  const total = criteria.reduce((sum, item) => sum + (Number(item.weight) || 0), 0);
  const unassigned = Math.max(0, 100 - total); // weight not given to any criterion yet

  return (
    <div className={`rubric ${compact ? "rubric-compact" : ""}`}>
      <div className="rubric-bar" role="img" aria-label="Rubric weights">
        {criteria.map((item, index) => (
          <i
            key={index}
            style={{
              flexGrow: Number(item.weight) || 0,
              background: RUBRIC_COLORS[index % RUBRIC_COLORS.length],
              animationDelay: `${index * 90}ms`,
            }}
            title={`${item.name}: ${item.weight}%`}
          />
        ))}
        {unassigned > 0 && <i className="rubric-open" style={{ flexGrow: unassigned }} title={`${unassigned}% not assigned yet`} />}
      </div>
      {!compact && (
        <ul className="rubric-legend">
          {criteria.map((item, index) => (
            <li key={index}>
              <i style={{ background: RUBRIC_COLORS[index % RUBRIC_COLORS.length] }} />
              {item.name || "Untitled"} <b className="num">{Number(item.weight) || 0}%</b>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
