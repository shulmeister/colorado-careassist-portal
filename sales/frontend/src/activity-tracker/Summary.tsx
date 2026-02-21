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
      <div className="container mx-auto max-w-7xl py-6 px-4">
        <ActivityNav />
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <div className="container mx-auto max-w-7xl py-6 px-4">
      <ActivityNav />
      <h1 className="text-2xl font-semibold mb-6 text-foreground">
        Sales KPI Dashboard
      </h1>

      {/* Forecast Revenue Banner */}
      <Card className="mb-6 border-green-500/30 bg-green-500/5">
        <CardContent className="p-6 flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">Pipeline Forecast Revenue</p>
            <p className="text-4xl font-bold text-green-500 mt-1">{currency("forecast_revenue")}</p>
            <p className="text-xs text-muted-foreground mt-1">{n("active_deals")} active deals in pipeline</p>
          </div>
          <div className="text-6xl opacity-20">$</div>
        </CardContent>
      </Card>

      {/* KPI Table: Weekly / Monthly / YTD */}
      <Card className="mb-6">
        <CardHeader className="pb-2">
          <CardTitle className="text-lg">Performance KPIs</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th className="text-left p-3 text-muted-foreground font-medium">Metric</th>
                <th className="text-right p-3 text-muted-foreground font-medium">This Week</th>
                <th className="text-right p-3 text-muted-foreground font-medium">This Month</th>
                <th className="text-right p-3 text-muted-foreground font-medium">YTD</th>
                <th className="text-right p-3 text-muted-foreground font-medium">All Time</th>
              </tr>
            </thead>
            <tbody>
              <KPIRow
                label="Visits"
                icon="📍"
                week={n("visits_this_week")}
                month={n("visits_this_month")}
                ytd={n("visits_ytd")}
                total={n("total_visits")}
              />
              <KPIRow
                label="New Contacts"
                icon="👤"
                week={n("new_contacts_this_week")}
                month={n("new_contacts_this_month")}
                ytd={n("new_contacts_ytd")}
                total={n("total_contacts")}
              />
              <KPIRow
                label="New Companies"
                icon="🏢"
                week={n("new_companies_this_week")}
                month={n("new_companies_this_month")}
                ytd={n("new_companies_ytd")}
                total={n("total_companies")}
              />
              <KPIRow
                label="New Deals"
                icon="🤝"
                week={n("new_deals_this_week")}
                month={n("new_deals_this_month")}
                ytd={n("new_deals_ytd")}
                total={n("total_deals")}
              />
              <KPIRow
                label="Active Deals"
                icon="📈"
                week=""
                month=""
                ytd=""
                total={n("active_deals")}
                highlight
              />
            </tbody>
          </table>
        </CardContent>
      </Card>

      {/* Activity KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <MiniKPI title="Emails Sent" value={n("emails_sent_7_days")} sub="Last 7 days" icon="📧" />
        <MiniKPI title="Phone Calls" value={n("phone_calls_7_days")} sub="Last 7 days" icon="📞" />
        <MiniKPI title="Visits (30d)" value={n("visits_last_30_days")} sub="Last 30 days" icon="🚗" />
        <MiniKPI title="Bonuses" value={"$" + n("total_bonuses")} sub="All time" icon="💰" />
      </div>

      <Card className="mb-6">
        <CardContent className="p-4">
          <p className="text-muted-foreground text-xs">
            Last updated:{" "}
            <span className="font-medium text-foreground/80">
              {data.last_updated ? new Date(String(data.last_updated)).toLocaleString() : "-"}
            </span>
          </p>
        </CardContent>
      </Card>

      <div className="mt-6">
        <h2 className="text-xl font-semibold mb-2 text-foreground">
          Upload Visits, Receipts, or Business Cards
        </h2>
        <UploadPanel showLegacyLink={false} />
      </div>
    </div>
  );
};

const KPIRow = ({
  label,
  icon,
  week,
  month,
  ytd,
  total,
  highlight,
}: {
  label: string;
  icon: string;
  week: string;
  month: string;
  ytd: string;
  total: string;
  highlight?: boolean;
}) => (
  <tr className={`border-b last:border-0 ${highlight ? "bg-primary/5" : ""}`}>
    <td className="p-3 font-medium">
      <span className="mr-2">{icon}</span>
      {label}
    </td>
    <td className="p-3 text-right font-semibold text-lg">{week || "-"}</td>
    <td className="p-3 text-right font-semibold text-lg">{month || "-"}</td>
    <td className="p-3 text-right font-semibold text-lg">{ytd || "-"}</td>
    <td className="p-3 text-right text-muted-foreground">{total}</td>
  </tr>
);

const MiniKPI = ({
  title,
  value,
  sub,
  icon,
}: {
  title: string;
  value: string;
  sub: string;
  icon: string;
}) => (
  <Card>
    <CardContent className="p-3">
      <div className="flex justify-between items-start">
        <p className="text-xs text-muted-foreground">{title}</p>
        <span className="text-lg">{icon}</span>
      </div>
      <p className="text-2xl font-bold mt-1">{value}</p>
      <p className="text-[0.6rem] text-muted-foreground">{sub}</p>
    </CardContent>
  </Card>
);

export default Summary;
export { Summary };
