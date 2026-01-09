import { required } from "ra-core";
import { ArrayInput } from "@/components/admin/array-input";
import { SelectInput } from "@/components/admin/select-input";
import { SimpleFormIterator } from "@/components/admin/simple-form-iterator";
import { TextInput } from "@/components/admin/text-input";
import { useIsMobile } from "@/hooks/use-mobile";
import { Avatar } from "./Avatar";

const statusChoices = [
  { id: "hot", name: "Hot" },
  { id: "warm", name: "Warm" },
  { id: "cold", name: "Cold" },
];

const contactTypeChoices = [
  { id: "prospect", name: "Prospect" },
  { id: "referral", name: "Referral" },
  { id: "client", name: "Client" },
];

export const ContactInputs = () => {
  const isMobile = useIsMobile();

  return (
    <div className={`flex flex-col gap-6 ${isMobile ? "" : "p-1"}`}>
      <div className="flex items-center gap-3">
        <Avatar />
        <div className="flex-1 grid gap-4 md:grid-cols-2">
          <TextInput source="name" label="Name" validate={required()} />
          <TextInput source="company" label="Company" />
          <TextInput source="email" label="Email" type="email" />
          <TextInput source="phone" label="Phone" />
        </div>
      </div>

      <div className={`grid gap-4 ${isMobile ? "" : "grid-cols-2"}`}>
        <TextInput source="address" label="Address" />
        <TextInput source="source" label="Source" />
        <SelectInput
          source="contact_type"
          label="Contact type"
          helperText={false}
          choices={contactTypeChoices}
        />
        <SelectInput
          source="status"
          label="Status"
          helperText={false}
          choices={statusChoices}
        />
      </div>

      <ArrayInput source="tags" label="Tags">
        <SimpleFormIterator disableAdd={false} disableReordering>
          <TextInput source="" label="Tag" />
        </SimpleFormIterator>
      </ArrayInput>

      <TextInput
        source="notes"
        label="Notes"
        multiline
        helperText={false}
        className="w-full"
      />
    </div>
  );
};
