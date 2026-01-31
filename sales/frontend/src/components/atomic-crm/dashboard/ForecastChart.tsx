import { ResponsiveBar } from "@nivo/bar";
import { format, startOfMonth, addMonths } from "date-fns";
import { TrendingUp } from "lucide-react";
import { useGetList } from "ra-core";
import { memo, useMemo } from "react";

import type { Deal } from "../types";

const DEFAULT_LOCALE = "en-US";
const CURRENCY = "USD";

// Probability multipliers by stage
const probabilityMultiplier = {
  opportunity: 0.2,
  "proposal-sent": 0.5,
  "in-negociation": 0.8,
  won: 1.0,
  delayed: 0.3,
  lost: 0,
};

export const ForecastChart = memo(() => {
  const acceptedLanguages = navigator
    ? navigator.languages || [navigator.language]
    : [DEFAULT_LOCALE];

  const { data, isPending } = useGetList<Deal>("deals", {
    pagination: { perPage: 500, page: 1 },
    sort: {
      field: "expected_closing_date",
      order: "ASC",
    },
    filter: {
      archived_at: null, // Only active deals
      "expected_closing_date@gte": new Date().toISOString(), // Future deals only
    },
  });

  const forecastByMonth = useMemo(() => {
    if (!data) return [];

    // Get next 6 months
    const months = [];
    for (let i = 0; i < 6; i++) {
      const month = startOfMonth(addMonths(new Date(), i));
      months.push({
        month,
        monthLabel: format(month, "MMM yyyy"),
        oneTime: 0,
        recurring: 0,
        weightedOneTime: 0,
        weightedRecurring: 0,
      });
    }

    // Group deals by expected closing month
    data.forEach((deal) => {
      if (!deal.expected_closing_date || deal.stage === "lost") return;

      const closeDate = new Date(deal.expected_closing_date);
      const dealMonth = startOfMonth(closeDate);

      const monthData = months.find(
        (m) => m.month.getTime() === dealMonth.getTime()
      );

      if (monthData && deal.amount) {
        const probability =
          probabilityMultiplier[deal.stage as keyof typeof probabilityMultiplier] ?? 0.2;

        if (deal.is_monthly_recurring) {
          monthData.recurring += deal.amount;
          monthData.weightedRecurring += deal.amount * probability;
        } else {
          monthData.oneTime += deal.amount;
          monthData.weightedOneTime += deal.amount * probability;
        }
      }
    });

    return months.map((m) => ({
      month: m.monthLabel,
      "One-Time": Math.round(m.weightedOneTime),
      "Recurring (MRR)": Math.round(m.weightedRecurring),
    }));
  }, [data]);

  if (isPending) return null;

  if (!data || data.length === 0) {
    return (
      <div className="flex flex-col">
        <div className="flex items-center mb-4">
          <div className="mr-3 flex">
            <TrendingUp className="text-muted-foreground w-6 h-6" />
          </div>
          <h2 className="text-xl font-semibold text-muted-foreground">
            Revenue Forecast
          </h2>
        </div>
        <div className="text-muted-foreground text-sm">
          No upcoming deals with expected close dates.
        </div>
      </div>
    );
  }

  const maxValue = Math.max(
    ...forecastByMonth.map((d) => d["One-Time"] + d["Recurring (MRR)"])
  );

  return (
    <div className="flex flex-col">
      <div className="flex items-center mb-4">
        <div className="mr-3 flex">
          <TrendingUp className="text-muted-foreground w-6 h-6" />
        </div>
        <h2 className="text-xl font-semibold text-muted-foreground">
          Revenue Forecast (Next 6 Months)
        </h2>
      </div>
      <div className="text-sm text-muted-foreground mb-4">
        Weighted by probability: Opportunity (20%), Proposal Sent (50%),
        Negotiation (80%), Won (100%)
      </div>
      <div className="h-[400px]">
        <ResponsiveBar
          data={forecastByMonth}
          indexBy="month"
          keys={["One-Time", "Recurring (MRR)"]}
          colors={["#3b82f6", "#10b981"]}
          margin={{ top: 30, right: 50, bottom: 60, left: 0 }}
          padding={0.3}
          valueScale={{
            type: "linear",
            min: 0,
            max: maxValue * 1.2,
          }}
          indexScale={{ type: "band", round: true }}
          enableGridX={false}
          enableGridY={true}
          enableLabel={true}
          label={(d) =>
            d.value > 0
              ? `${(d.value / 1000).toFixed(0)}k`
              : ""
          }
          labelTextColor="#fff"
          tooltip={({ id, value, indexValue }) => (
            <div className="p-2 bg-secondary rounded shadow inline-flex items-center gap-1 text-secondary-foreground">
              <strong>
                {indexValue} - {id}:
              </strong>
              &nbsp;
              {value.toLocaleString(acceptedLanguages.at(0) ?? DEFAULT_LOCALE, {
                style: "currency",
                currency: CURRENCY,
              })}
            </div>
          )}
          axisTop={null}
          axisBottom={{
            tickSize: 0,
            tickPadding: 12,
            tickRotation: -45,
            legendPosition: "middle",
            legendOffset: 50,
            style: {
              ticks: {
                text: {
                  fill: "var(--color-muted-foreground)",
                },
              },
            },
          }}
          axisLeft={null}
          axisRight={{
            format: (v: any) =>
              v >= 1000 ? `$${Math.abs(v / 1000)}k` : `$${v}`,
            tickValues: 5,
            style: {
              ticks: {
                text: {
                  fill: "var(--color-muted-foreground)",
                },
              },
            },
          }}
          legends={[
            {
              dataFrom: "keys",
              anchor: "top-left",
              direction: "row",
              justify: false,
              translateX: 0,
              translateY: -30,
              itemsSpacing: 20,
              itemWidth: 120,
              itemHeight: 20,
              itemDirection: "left-to-right",
              symbolSize: 12,
              symbolShape: "square",
              effects: [
                {
                  on: "hover",
                  style: {
                    itemOpacity: 1,
                  },
                },
              ],
            },
          ]}
        />
      </div>
    </div>
  );
});
