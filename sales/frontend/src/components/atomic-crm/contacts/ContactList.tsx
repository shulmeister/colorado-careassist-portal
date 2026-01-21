import jsonExport from "jsonexport/dist";
import {
  downloadCSV,
  useGetIdentity,
  useListContext,
  type Exporter,
} from "ra-core";
import { BulkActionsToolbar } from "@/components/admin/bulk-actions-toolbar";
import { BulkDeleteButton } from "@/components/admin/bulk-delete-button";
import { BulkExportButton } from "@/components/admin/bulk-export-button";
import { BulkMergeButton } from "@/components/admin/bulk-merge-button";
import { CreateButton } from "@/components/admin/create-button";
import { ExportButton } from "@/components/admin/export-button";
import { List } from "@/components/admin/list";
import { SortButton } from "@/components/admin/sort-button";
import { Card } from "@/components/ui/card";

import type { Contact } from "../types";
import { ContactEmpty } from "./ContactEmpty";
import { ContactImportButton } from "./ContactImportButton";
import { ContactListContent } from "./ContactListContent";
import { ContactListFilter } from "./ContactListFilter";
import { TopToolbar } from "../layout/TopToolbar";

export const ContactList = () => {
  const { identity } = useGetIdentity();

  if (!identity) return null;

  return (
    <List
      title={false}
      actions={<ContactListActions />}
      perPage={25}
      sort={{ field: "last_activity", order: "DESC" }}
      exporter={exporter}
    >
      <ContactListLayout />
    </List>
  );
};

const ContactListLayout = () => {
  const { data, isPending, filterValues } = useListContext();
  const { identity } = useGetIdentity();

  const hasFilters = filterValues && Object.keys(filterValues).length > 0;

  if (!identity || isPending) return null;

  if (!data?.length && !hasFilters) return <ContactEmpty />;

  return (
    <div className="flex flex-row gap-8">
      <ContactListFilter />
      <div className="w-full flex flex-col gap-4">
        <Card className="py-0">
          <ContactListContent />
        </Card>
      </div>
      <BulkActionsToolbar>
        <BulkMergeButton />
        <BulkExportButton />
        <BulkDeleteButton />
      </BulkActionsToolbar>
    </div>
  );
};

const ContactListActions = () => (
  <TopToolbar>
    <SortButton fields={["name", "last_activity", "created_at"]} />
    <ContactImportButton />
    <ExportButton exporter={exporter} />
    <CreateButton />
  </TopToolbar>
);

const exporter: Exporter<Contact> = async (records, fetchRelatedRecords) => {
  const contacts = records.map((contact) => {
    const tags = Array.isArray(contact.tags)
      ? contact.tags.join(", ")
      : contact.tags;
    return {
      id: contact.id,
      name: contact.name || `${contact.first_name || ""} ${contact.last_name || ""}`.trim(),
      company: contact.company,
      email: contact.email,
      phone: contact.phone,
      address: contact.address,
      status: contact.status,
      contact_type: contact.contact_type,
      tags,
      source: contact.source,
      last_activity: contact.last_activity,
      created_at: contact.created_at,
    };
  });
  return jsonExport(contacts, {}, (_err: any, csv: string) => {
    downloadCSV(csv, "contacts");
  });
};
