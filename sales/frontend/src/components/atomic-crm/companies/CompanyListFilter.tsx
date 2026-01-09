import { Building, Truck, Users } from "lucide-react";
import { FilterLiveForm, useGetIdentity } from "ra-core";
import { ToggleFilterButton } from "@/components/admin/toggle-filter-button";
import { SearchInput } from "@/components/admin/search-input";

import { FilterCategory } from "../filters/FilterCategory";
import { REFERRAL_CATEGORIES, SERVICE_AREAS } from "./referralData";

export const CompanyListFilter = () => {
  const { identity } = useGetIdentity();
  return (
    <div className="w-52 min-w-52 flex flex-col gap-8">
      <FilterLiveForm>
        <SearchInput source="q" />
      </FilterLiveForm>

      <FilterCategory
        icon={<Building className="h-4 w-4" />}
        label="Service Area / County"
      >
        {SERVICE_AREAS.map((area) => (
          <ToggleFilterButton
            key={area}
            className="w-full justify-between"
            label={area}
            value={{ size: area }}
          />
        ))}
      </FilterCategory>

      <FilterCategory icon={<Truck className="h-4 w-4" />} label="Referral Type">
        <div className="flex flex-col gap-4">
          {REFERRAL_CATEGORIES.map((category) => (
            <div key={category.label} className="flex flex-col gap-1">
              <p className="text-xs uppercase tracking-wide text-secondary-foreground/70">
                {category.label}
              </p>
              {category.types.map((type) => (
                <ToggleFilterButton
                  key={type}
                  className="w-full justify-between"
                  label={type}
                  value={{ sector: type }}
                />
              ))}
            </div>
          ))}
        </div>
      </FilterCategory>

      <FilterCategory
        icon={<Users className="h-4 w-4" />}
        label="Account Manager"
      >
        <ToggleFilterButton
          className="w-full justify-between"
          label={"Me"}
          value={{ sales_id: identity?.id }}
        />
      </FilterCategory>
    </div>
  );
};
