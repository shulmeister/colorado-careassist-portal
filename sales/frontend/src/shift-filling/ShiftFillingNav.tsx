import { Link, useLocation } from "react-router";

const shiftFillingRoutes = [
  { to: "/shift-filling", label: "Dashboard" },
  { to: "/shift-filling/sms-log", label: "SMS Log" },
];

export const ShiftFillingNav = () => {
  const location = useLocation();

  return (
    <div className="flex flex-wrap gap-2 mb-6">
      {shiftFillingRoutes.map((route) => {
        const isActive =
          route.to === "/shift-filling"
            ? location.pathname === "/shift-filling"
            : location.pathname.startsWith(route.to);
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

export default ShiftFillingNav;
