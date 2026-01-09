import { Link, useLocation } from "react-router";

const activityRoutes = [
  { to: "/activity/summary", label: "Summary" },
  { to: "/activity/visits", label: "Visits" },
  { to: "/activity/expenses", label: "Expenses" },
  { to: "/activity/uploads", label: "Uploads" },
  { to: "/activity/logs", label: "Activity Logs" },
];

export const ActivityNav = () => {
  const location = useLocation();

  return (
    <div className="flex flex-wrap gap-2 mb-6">
      {activityRoutes.map((route) => {
        const isActive = location.pathname.startsWith(route.to);
        return (
          <Link
            key={route.to}
            to={route.to}
            className={`px-4 py-2 text-sm font-medium rounded-md border transition-colors ${
              isActive
                ? "bg-secondary text-secondary-foreground border-secondary-foreground"
                : "text-secondary-foreground/70 border-border hover:text-secondary-foreground"
            }`}
          >
            {route.label}
          </Link>
        );
      })}
    </div>
  );
};

export default ActivityNav;

