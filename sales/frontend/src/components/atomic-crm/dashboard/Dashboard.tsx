import { useGetList } from "ra-core";

import type { Contact, ContactNote } from "../types";
import { DashboardActivityLog } from "./DashboardActivityLog";
import { DashboardStepper } from "./DashboardStepper";
import { DealsChart } from "./DealsChart";
import { ForecastChart } from "./ForecastChart";
import { HotContacts } from "./HotContacts";
import { TasksList } from "./TasksList";
import { Welcome } from "./Welcome";

export const Dashboard = () => {
  const { total: totalDeal, isPending: isPendingDeal } = useGetList<Contact>(
    "deals",
    {
      pagination: { page: 1, perPage: 1 },
    },
  );

  if (isPendingDeal) {
    return null;
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-12 gap-6 mt-1">
      <div className="md:col-span-3">
        <div className="flex flex-col gap-4">
          <HotContacts />
        </div>
      </div>
      <div className="md:col-span-6">
        <div className="flex flex-col gap-6">
          <ForecastChart />
          <DealsChart />
          <DashboardActivityLog />
        </div>
      </div>

      <div className="md:col-span-3">
        <TasksList />
      </div>
    </div>
  );
};
