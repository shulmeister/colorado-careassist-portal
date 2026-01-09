import { endOfYesterday, startOfMonth, startOfWeek, subMonths } from "date-fns";
import { FilterLiveForm } from "ra-core";
import { Clock, Tag, TrendingUp, Users } from "lucide-react";
import { SearchInput } from "@/components/admin/search-input";
import { ToggleFilterButton } from "@/components/admin/toggle-filter-button";
import { Badge } from "@/components/ui/badge";

import { FilterCategory } from "../filters/FilterCategory";
import { Status } from "../misc/Status";

export const ContactListFilter = () => {
  return (
    <div className="w-52 min-w-52 order-first pt-0.75 flex flex-col gap-4">
      <FilterLiveForm>
        <SearchInput source="q" />
      </FilterLiveForm>

      <FilterCategory label="Last activity" icon={<Clock />}>
        <ToggleFilterButton
          className="w-full justify-between"
          label="Today"
          value={{
            "last_activity@gte": endOfYesterday().toISOString(),
            "last_activity@lte": undefined,
          }}
        />
        <ToggleFilterButton
          className="w-full justify-between"
          label="This week"
          value={{
            "last_activity@gte": startOfWeek(new Date()).toISOString(),
            "last_activity@lte": undefined,
          }}
        />
        <ToggleFilterButton
          className="w-full justify-between"
          label="Before this week"
          value={{
            "last_activity@gte": undefined,
            "last_activity@lte": startOfWeek(new Date()).toISOString(),
          }}
        />
        <ToggleFilterButton
          className="w-full justify-between"
          label="Before this month"
          value={{
            "last_activity@gte": undefined,
            "last_activity@lte": startOfMonth(new Date()).toISOString(),
          }}
        />
        <ToggleFilterButton
          className="w-full justify-between"
          label="Before last month"
          value={{
            "last_activity@gte": undefined,
            "last_activity@lte": subMonths(
              startOfMonth(new Date()),
              1,
            ).toISOString(),
          }}
        />
      </FilterCategory>

      <FilterCategory label="Status" icon={<TrendingUp />}>
        {["hot", "warm", "cold"].map((status) => (
          <ToggleFilterButton
            key={status}
            className="w-full justify-between"
            label={
              <span>
                {status} <Status status={status} />
              </span>
            }
            value={{ status }}
          />
        ))}
      </FilterCategory>

      <FilterCategory label="Tags" icon={<Tag />}>
        {["Prospect", "Referral Source", "Client"].map((tag) => (
          <ToggleFilterButton
            className="w-full justify-between"
            key={tag}
            label={
              <Badge
                variant="secondary"
                className="text-black text-xs font-normal cursor-pointer"
              >
                {tag}
              </Badge>
            }
            value={{ tags: tag }}
          />
        ))}
      </FilterCategory>

      <FilterCategory icon={<Users />} label="Account Manager">
        <ToggleFilterButton
          className="w-full justify-between"
          label={"Prospects"}
          value={{ contact_type: "prospect" }}
        />
        <ToggleFilterButton
          className="w-full justify-between"
          label={"Referrals"}
          value={{ contact_type: "referral" }}
        />
        <ToggleFilterButton
          className="w-full justify-between"
          label={"Clients"}
          value={{ contact_type: "client" }}
        />
      </FilterCategory>
    </div>
  );
};
