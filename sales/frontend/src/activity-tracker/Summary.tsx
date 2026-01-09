import { useEffect, useState } from "react";
import { ActivityNav } from "./ActivityNav";
import { UploadPanel } from "./UploadPanel";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type SummaryStats = {
  // Visits
  totalVisits: string;
  visitsThisMonth: string;
  // Contacts
  totalContacts: string;
  newContactsThisMonth: string;
  newContactsLast7Days: string;
  // Companies
  totalCompanies: string;
  newCompaniesThisMonth: string;
  // Deals
  totalDeals: string;
  activeDeals: string;
  newDealsThisMonth: string;
  // Activity
  emailsSent: string;
  phoneCalls: string;
  lastUpdated: string;
};

const initialStats: SummaryStats = {
  totalVisits: "-",
  visitsThisMonth: "-",
  totalContacts: "-",
  newContactsThisMonth: "-",
  newContactsLast7Days: "-",
  totalCompanies: "-",
  newCompaniesThisMonth: "-",
  totalDeals: "-",
  activeDeals: "-",
  newDealsThisMonth: "-",
  emailsSent: "-",
  phoneCalls: "-",
  lastUpdated: "-",
};

const Summary = () => {
  const [stats, setStats] = useState<SummaryStats>(initialStats);

  useEffect(() => {
    const fetchSummaryData = async () => {
      try {
        const summaryRes = await fetch("/api/dashboard/summary", {
          credentials: "include",
        });
        if (!summaryRes.ok) {
          throw new Error("Failed to fetch summary");
        }
        const summary = await summaryRes.json();
        setStats({
          totalVisits: Number(summary.total_visits || 0).toLocaleString(),
          visitsThisMonth: Number(summary.visits_this_month || 0).toLocaleString(),
          totalContacts: Number(summary.total_contacts || 0).toLocaleString(),
          newContactsThisMonth: Number(summary.new_contacts_this_month || 0).toLocaleString(),
          newContactsLast7Days: Number(summary.new_contacts_last_7_days || 0).toLocaleString(),
          totalCompanies: Number(summary.total_companies || 0).toLocaleString(),
          newCompaniesThisMonth: Number(summary.new_companies_this_month || 0).toLocaleString(),
          totalDeals: Number(summary.total_deals || 0).toLocaleString(),
          activeDeals: Number(summary.active_deals || 0).toLocaleString(),
          newDealsThisMonth: Number(summary.new_deals_this_month || 0).toLocaleString(),
          emailsSent: summary.emails_sent_7_days != null
            ? Number(summary.emails_sent_7_days).toLocaleString()
            : "-",
          phoneCalls: summary.phone_calls_7_days != null
            ? Number(summary.phone_calls_7_days).toLocaleString()
            : "-",
          lastUpdated: summary.last_updated || "-",
        });
      } catch (error) {
        console.error("Error fetching summary data:", error);
        setStats(initialStats);
      }
    };

    fetchSummaryData();
  }, []);

  return (
    <div className="container mx-auto max-w-7xl py-6 px-4">
      <ActivityNav />
      <h1 className="text-2xl font-semibold mb-6 text-foreground">
        Sales Activity Dashboard
      </h1>
      
      {/* Main KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
        <KPICard 
          title="Total Visits" 
          value={stats.totalVisits} 
          icon="📍"
          subtitle="All time"
        />
        <KPICard 
          title="Visits This Month" 
          value={stats.visitsThisMonth} 
          icon="📊"
        />
        <KPICard 
          title="New Contacts" 
          value={stats.newContactsThisMonth} 
          icon="👤"
          subtitle="This month"
          highlight
        />
        <KPICard 
          title="New Companies" 
          value={stats.newCompaniesThisMonth} 
          icon="🏢"
          subtitle="This month"
          highlight
        />
        <KPICard 
          title="New Deals" 
          value={stats.newDealsThisMonth} 
          icon="🤝"
          subtitle="This month"
          highlight
        />
        <KPICard 
          title="Active Deals" 
          value={stats.activeDeals} 
          icon="📈"
          subtitle="In pipeline"
        />
      </div>

      {/* Secondary KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 mb-6">
        <KPICard 
          title="Total Contacts" 
          value={stats.totalContacts} 
          icon="📇"
          small
        />
        <KPICard 
          title="Total Companies" 
          value={stats.totalCompanies} 
          icon="🏛️"
          small
        />
        <KPICard 
          title="Total Deals" 
          value={stats.totalDeals} 
          icon="💼"
          small
        />
        <KPICard 
          title="Emails Sent" 
          value={stats.emailsSent} 
          icon="📧"
          subtitle="Last 7 days"
          small
        />
        <KPICard 
          title="Phone Calls" 
          value={stats.phoneCalls} 
          icon="📞"
          subtitle="Last 7 days"
          small
        />
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Activity Overview</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground text-sm leading-relaxed">
            Track your sales team's performance with key metrics: visits, new contacts scanned, 
            companies added, and deals in progress. Use the tabs above to view detailed visits, 
            manage uploads, or check activity logs.
          </p>
          <p className="text-muted-foreground text-xs mt-3">
            Last updated:{" "}
            <span className="font-medium text-foreground/80">
              {stats.lastUpdated !== "-" 
                ? new Date(stats.lastUpdated).toLocaleString() 
                : "-"}
            </span>
          </p>
        </CardContent>
      </Card>

      <div className="mt-6">
        <h2 className="text-xl font-semibold mb-2 text-foreground">
          Upload Visits, Receipts, or Business Cards
        </h2>
        <p className="text-muted-foreground text-sm mb-4">
          Upload MyWay route PDFs (visits + mileage), time tracking PDFs, receipt photos/PDFs (expenses),
          or business card photos. We'll parse them automatically and update your tracker and reimbursements.
        </p>
        <UploadPanel showLegacyLink={false} />
      </div>
    </div>
  );
};

const KPICard = ({
  title,
  value,
  icon,
  subtitle,
  highlight,
  small,
}: {
  title: string;
  value: string;
  icon: string;
  subtitle?: string;
  highlight?: boolean;
  small?: boolean;
}) => (
  <Card className={`h-full ${highlight ? 'border-primary/50 bg-primary/5' : ''}`}>
    <CardContent className={small ? "p-3" : "p-4"}>
      <div className="flex justify-between items-start mb-2">
        <div className="flex-1">
          <p className={`text-muted-foreground mb-1 ${small ? 'text-[0.65rem]' : 'text-xs'}`}>
            {title}
          </p>
          {subtitle && (
            <p className="text-[0.6rem] text-muted-foreground/70">
              {subtitle}
            </p>
          )}
        </div>
        <div className={`bg-primary/10 rounded-lg ${small ? 'p-1.5 text-lg' : 'p-2 text-2xl'}`}>
          {icon}
        </div>
      </div>
      <p className={`font-bold text-foreground mt-2 ${small ? 'text-xl' : 'text-3xl'}`}>
        {value}
      </p>
    </CardContent>
  </Card>
);

export default Summary;
export { Summary };
