import { formatDistance } from "date-fns";
import { DollarSign, Pencil, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import {
  RecordContextProvider,
  ShowBase,
  useRecordContext,
  useShowContext,
} from "ra-core";
import { Link as RouterLink, useLocation } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

import { ActivityLog } from "../activity/ActivityLog";
import { findDealLabel } from "../deals/deal";
import { Status } from "../misc/Status";
import { useConfigurationContext } from "../root/ConfigurationContext";
import type { Contact, Deal } from "../types";
import { Avatar } from "./Avatar";
import { ContactAside } from "./ContactAside";
import { TagsList } from "./TagsList";
import { ContactTasksList } from "./ContactTasksList";

// Status colors matching the filter sidebar
const STATUS_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  hot: { bg: "bg-red-500/20", text: "text-red-400", border: "border-red-500/50" },
  warm: { bg: "bg-yellow-500/20", text: "text-yellow-400", border: "border-yellow-500/50" },
  cold: { bg: "bg-blue-500/20", text: "text-blue-400", border: "border-blue-500/50" },
};

export const ContactShow = () => (
  <ShowBase>
    <ContactShowContent />
  </ShowBase>
);

const ContactShowContent = () => {
  const { record, isPending } = useShowContext<Contact>();
  if (isPending || !record) return null;

  const displayName =
    record.name ||
    `${record.first_name || ""} ${record.last_name || ""}`.trim() ||
    "Unnamed contact";

  const statusStyle = record.status ? STATUS_COLORS[record.status] : null;

  // Count deals (from record if available)
  const dealCount = (record as any).nb_deals || 0;

  return (
    <div className="mt-2 mb-2 flex gap-8">
      <div className="flex-1">
        <Card>
          <CardContent className="flex flex-col gap-4">
            {/* Edit button */}
            <div className="flex justify-end">
              <Button variant="outline" size="sm" asChild>
                <RouterLink to={`/contacts/${record.id}`} className="flex items-center gap-2">
                  <Pencil className="h-4 w-4" />
                  Edit
                </RouterLink>
              </Button>
            </div>

            {/* Header with avatar and basic info */}
            <div className="flex items-center gap-3">
              <Avatar />
              <div className="flex-1">
                <h5 className="text-xl font-semibold">{displayName}</h5>
                <div className="text-sm text-muted-foreground">
                  {[record.company, record.title].filter(Boolean).join(" • ")}
                </div>
                <div className="flex gap-2 mt-2 flex-wrap">
                  {record.contact_type && (
                    <Badge variant="secondary" className="text-xs font-normal">
                      {record.contact_type}
                    </Badge>
                  )}
                  {record.status && (
                    <Badge 
                      variant="outline" 
                      className={`text-xs font-medium ${
                        statusStyle 
                          ? `${statusStyle.bg} ${statusStyle.text} ${statusStyle.border}` 
                          : ""
                      }`}
                    >
                      <Status status={record.status} className="mr-1" />
                      {record.status}
                    </Badge>
                  )}
                  <TagsList />
                </div>
              </div>
            </div>

            {/* Contact details */}
            <div className="grid md:grid-cols-2 gap-3">
              <Detail label="Email" value={record.email} />
              <Detail label="Phone" value={record.phone} />
              <Detail label="Address" value={record.address} />
              <Detail label="Source" value={record.source} />
            </div>

            {record.notes && (
              <div>
                <div className="text-sm text-muted-foreground mb-1">Notes</div>
                <div className="whitespace-pre-wrap text-sm">{record.notes}</div>
              </div>
            )}

            {/* Tabs for Activity, Deals, Tasks */}
            <Tabs defaultValue="activity" className="mt-4">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="activity">Activity</TabsTrigger>
                <TabsTrigger value="deals">
                  {dealCount > 0 
                    ? dealCount === 1 
                      ? "1 Deal" 
                      : `${dealCount} Deals`
                    : "Deals"}
                </TabsTrigger>
                <TabsTrigger value="tasks">Tasks</TabsTrigger>
              </TabsList>

              <TabsContent value="activity" className="pt-2">
                <ActivityLog contactId={record.id} context="contact" />
              </TabsContent>

              <TabsContent value="deals" className="pt-2">
                <ContactDealsContent contactId={record.id} companyId={record.company_id} />
              </TabsContent>

              <TabsContent value="tasks" className="pt-2">
                <ContactTasksList contactId={record.id} />
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>
      <ContactAside />
    </div>
  );
};

const ContactDealsContent = ({ contactId, companyId }: { contactId: number; companyId?: number }) => {
  const [deals, setDeals] = useState<Deal[]>([]);
  const [isPending, setIsPending] = useState(true);
  const { dealStages } = useConfigurationContext();
  const location = useLocation();

  // Fetch deals for this specific contact
  useEffect(() => {
    const fetchDeals = async () => {
      try {
        // Fetch all deals and filter client-side for those containing this contact_id
        const response = await fetch(`/sales/admin/deals`);
        if (response.ok) {
          const data = await response.json();
          const allDeals = data.data || data || [];
          // Filter deals that include this contact_id in their contact_ids array
          const contactDeals = allDeals.filter((deal: any) => {
            if (!deal.contact_ids) return false;
            const ids = typeof deal.contact_ids === 'string' 
              ? JSON.parse(deal.contact_ids) 
              : deal.contact_ids;
            return Array.isArray(ids) && ids.includes(contactId);
          });
          setDeals(contactDeals);
        }
      } catch (err) {
        console.error("Error fetching deals:", err);
      } finally {
        setIsPending(false);
      }
    };
    fetchDeals();
  }, [contactId]);

  if (isPending) return <div className="py-4 text-muted-foreground">Loading deals...</div>;

  const now = Date.now();

  return (
    <div className="flex flex-col gap-2">
      {/* Add Deal button */}
      <div className="flex justify-end mb-2">
        <Button variant="outline" size="sm" asChild>
          <RouterLink 
            to="/deals/create" 
            state={{ record: { contact_id: contactId, company_id: companyId } }}
            className="flex items-center gap-2"
          >
            <Plus className="h-4 w-4" />
            Add Deal
          </RouterLink>
        </Button>
      </div>

      {deals && deals.length > 0 ? (
        <div className="divide-y">
          {deals.map((deal) => (
            <RecordContextProvider key={deal.id} value={deal}>
              <RouterLink
                to={`/deals/${deal.id}/show`}
                state={{ from: location.pathname }}
                className="flex items-center justify-between hover:bg-muted py-3 px-2 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-green-500/20 flex items-center justify-center">
                    <DollarSign className="w-4 h-4 text-green-500" />
                  </div>
                  <div>
                    <div className="font-medium">{deal.name}</div>
                    <div className="text-sm text-muted-foreground">
                      {findDealLabel(dealStages, deal.stage)}
                      {deal.amount ? ` • ${deal.amount.toLocaleString("en-US", {
                        style: "currency",
                        currency: "USD",
                        minimumFractionDigits: 0,
                      })}` : ""}
                    </div>
                  </div>
                </div>
                {deal.created_at && (
                  <div className="text-sm text-muted-foreground">
                    {formatDistance(new Date(deal.created_at), now, { addSuffix: true })}
                  </div>
                )}
              </RouterLink>
            </RecordContextProvider>
          ))}
        </div>
      ) : (
        <div className="py-8 text-center text-muted-foreground">
          No deals yet for this contact
        </div>
      )}
    </div>
  );
};

const Detail = ({ label, value }: { label: string; value?: string | null }) =>
  value ? (
    <div>
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className="text-sm">{value}</div>
    </div>
  ) : null;
