import { useEffect, useState } from "react";
import { ActivityNav } from "./ActivityNav";
import { UploadPanel } from "./UploadPanel";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type DashboardData = Record<string, number | string>;

const Summary = () => {
  const [data, setData] = useState<DashboardData>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch("api/dashboard/summary", { credentials: "include" });
        if (res.ok) setData(await res.json());
      } catch (e) {
        console.error("Error fetching summary:", e);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const n = (key: string) => {
    const v = data[key];
    return v != null ? Number(v).toLocaleString() : "-";
  };

  const currency = (key: string) => {
    const v = data[key];
    return v != null
      ? "$" + Number(v).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })
      : "-";
  };

  if (loading) {
    return (
      <div className="container mx-auto max-w-7xl py-3 px-4">
        <ActivityNav />
        <p className="text-muted-foreground text-sm">Loading...</p>
      </div>
    );
  }

  return (
    <div className="container mx-auto max-w-7xl py-3 px-4">
      <ActivityNav />

      {/* Header row: title + forecast */}
      <div className="flex items-center justify-between mb-3">
        <h1 className="text-lg font-semibold text-foreground">Sales KPIs</h1>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-muted-foreground">Pipeline:</span>
          <span className="font-bold text-green-500 text-lg">{currency("forecast_revenue")}</span>
          <span className="text-muted-foreground text-xs">({n("active_deals")} deals)</span>
        </div>
      </div>

      {/* Main KPI Table */}
      <Card className="mb-3">
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/30">
                <th className="text-left py-2 px-3 text-muted-foreground font-medium text-xs">Metric</th>
                <th className="text-right py-2 px-3 text-muted-foreground font-medium text-xs">Week</th>
                <th className="text-right py-2 px-3 text-muted-foreground font-medium text-xs">Month</th>
                <th className="text-right py-2 px-3 text-muted-foreground font-medium text-xs">YTD</th>
                <th className="text-right py-2 px-3 text-muted-foreground font-medium text-xs">All Time</th>
              </tr>
            </thead>
            <tbody>
              <KPIRow label="Visits" icon="📍"
                week={n("visits_this_week")} month={n("visits_this_month")}
                ytd={n("visits_ytd")} total={n("total_visits")} />
              <KPIRow label="New Contacts" icon="👤"
                week={n("new_contacts_this_week")} month={n("new_contacts_this_month")}
                ytd={n("new_contacts_ytd")} total={n("total_contacts")} />
              <KPIRow label="New Companies" icon="🏢"
                week={n("new_companies_this_week")} month={n("new_companies_this_month")}
                ytd={n("new_companies_ytd")} total={n("total_companies")} />
              <KPIRow label="New Deals" icon="🤝"
                week={n("new_deals_this_week")} month={n("new_deals_this_month")}
                ytd={n("new_deals_ytd")} total={n("total_deals")} />
              <KPIRow label="Active Deals" icon="📈"
                week="" month="" ytd="" total={n("active_deals")} highlight />
            </tbody>
          </table>
        </CardContent>
      </Card>

      {/* Closed Deals + Activity row */}
      <div className="grid grid-cols-2 sm:grid-cols-6 gap-2 mb-3">
        <MiniKPI title="Closed This Q" value={n("closed_deals_this_quarter")} icon="✅" highlight />
        <MiniKPI title="Closed Last Q" value={n("closed_deals_last_quarter")} icon="📋" />
        <MiniKPI title="Visits (30d)" value={n("visits_last_30_days")} icon="🚗" />
        <MiniKPI title="Emails (7d)" value={n("emails_sent_7_days")} icon="📧" />
        <MiniKPI title="Calls (7d)" value={n("phone_calls_7_days")} icon="📞" />
        <MiniKPI title="Bonuses" value={"$" + n("total_bonuses")} icon="💰" />
      </div>

      {/* Last updated */}
      <p className="text-[0.65rem] text-muted-foreground/60 mb-3">
        Updated: {data.last_updated ? new Date(String(data.last_updated)).toLocaleString() : "-"}
      </p>

      {/* Upload Panel */}
      <details className="mb-3">
        <summary className="text-sm font-medium text-foreground cursor-pointer hover:text-primary">
          Upload Visits, Receipts, or Business Cards
        </summary>
        <div className="mt-2">
          <UploadPanel showLegacyLink={false} />
        </div>
      </details>
    </div>
  );
};

const KPIRow = ({
  label, icon, week, month, ytd, total, highlight,
}: {
  label: string; icon: string; week: string; month: string;
  ytd: string; total: string; highlight?: boolean;
}) => (
  <tr className={`border-b last:border-0 ${highlight ? "bg-primary/5" : "hover:bg-muted/20"}`}>
    <td className="py-1.5 px-3 font-medium text-sm">
      <span className="mr-1.5">{icon}</span>{label}
    </td>
    <td className="py-1.5 px-3 text-right font-semibold">{week || "-"}</td>
    <td className="py-1.5 px-3 text-right font-semibold">{month || "-"}</td>
    <td className="py-1.5 px-3 text-right font-bold text-primary">{ytd || "-"}</td>
    <td className="py-1.5 px-3 text-right text-muted-foreground text-xs">{total}</td>
  </tr>
);

const MiniKPI = ({
  title, value, icon, highlight,
}: {
  title: string; value: string; icon: string; highlight?: boolean;
}) => (
  <Card className={highlight ? "border-green-500/40 bg-green-500/5" : ""}>
    <CardContent className="p-2 text-center">
      <p className="text-[0.6rem] text-muted-foreground mb-0.5">{icon} {title}</p>
      <p className="text-lg font-bold">{value}</p>
    </CardContent>
  </Card>
);

export default Summary;
export { Summary };
