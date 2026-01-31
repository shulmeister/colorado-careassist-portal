import { required, useRecordContext } from "ra-core";
import { AutocompleteArrayInput } from "@/components/admin/autocomplete-array-input";
import { ReferenceArrayInput } from "@/components/admin/reference-array-input";
import { ReferenceInput } from "@/components/admin/reference-input";
import { TextInput } from "@/components/admin/text-input";
import { NumberInput } from "@/components/admin/number-input";
import { DateInput } from "@/components/admin/date-input";
import { SelectInput } from "@/components/admin/select-input";
import { BooleanInput } from "@/components/admin/boolean-input";
import { Separator } from "@/components/ui/separator";
import { useIsMobile } from "@/hooks/use-mobile";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import { useFormContext } from "react-hook-form";

import { contactOptionText } from "../misc/ContactOption";
import { useConfigurationContext } from "../root/ConfigurationContext";
import { AutocompleteCompanyInput } from "../companies/AutocompleteCompanyInput.tsx";

export const DealInputs = () => {
  const isMobile = useIsMobile();
  return (
    <div className="flex flex-col gap-8">
      <DealInfoInputs />

      <div className={`flex gap-6 ${isMobile ? "flex-col" : "flex-row"}`}>
        <DealLinkedToInputs />
        <Separator orientation={isMobile ? "horizontal" : "vertical"} />
        <DealMiscInputs />
      </div>
    </div>
  );
};

const DealInfoInputs = () => {
  return (
    <div className="flex flex-col gap-4 flex-1">
      <TextInput
        source="name"
        label="Deal name"
        validate={required()}
        helperText={false}
      />
      <TextInput source="description" multiline rows={3} helperText={false} />
    </div>
  );
};

const DealLinkedToInputs = () => {
  return (
    <div className="flex flex-col gap-4 flex-1">
      <h3 className="text-base font-medium">Linked to</h3>
      <ReferenceInput source="company_id" reference="companies">
        <AutocompleteCompanyInput />
      </ReferenceInput>

      <ReferenceArrayInput source="contact_ids" reference="contacts_summary">
        <AutocompleteArrayInput
          label="Contacts"
          optionText={contactOptionText}
          helperText={false}
        />
      </ReferenceArrayInput>
    </div>
  );
};

const DealMiscInputs = () => {
  const { dealStages, dealCategories } = useConfigurationContext();
  const { setValue } = useFormContext();

  const setDatePreset = (days: number) => {
    const date = new Date();
    date.setDate(date.getDate() + days);
    setValue("expected_closing_date", date.toISOString().split("T")[0]);
  };

  return (
    <div className="flex flex-col gap-4 flex-1">
      <h3 className="text-base font-medium">Misc</h3>

      <SelectInput
        source="category"
        label="Est. Weekly Hours"
        choices={dealCategories.map((type) => ({
          id: type,
          name: type,
        }))}
        helperText={false}
      />

      <div className="flex flex-col gap-2">
        <NumberInput
          source="amount"
          label="Revenue Amount"
          defaultValue={0}
          helperText={false}
          validate={required()}
        />
        <BooleanInput
          source="is_monthly_recurring"
          label="Monthly Recurring Revenue (MRR)"
          defaultValue={false}
          helperText="Check if this is a monthly recurring revenue deal"
        />
      </div>

      <div className="flex flex-col gap-2">
        <DateInput
          validate={required()}
          source="expected_closing_date"
          label="Expected Close Date"
          helperText={false}
          defaultValue={new Date().toISOString().split("T")[0]}
        />
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setDatePreset(7)}
          >
            Next Week
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setDatePreset(30)}
          >
            Next Month
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setDatePreset(90)}
          >
            Next Quarter
          </Button>
        </div>
      </div>

      <SelectInput
        source="stage"
        choices={dealStages.map((stage) => ({
          id: stage.value,
          name: stage.label,
        }))}
        defaultValue="opportunity"
        helperText={false}
        validate={required()}
      />
    </div>
  );
};
