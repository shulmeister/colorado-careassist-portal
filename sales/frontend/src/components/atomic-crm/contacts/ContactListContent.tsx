import { formatRelative } from "date-fns";
import { TextField } from "@/components/admin/text-field";
import { DataTable } from "@/components/admin/data-table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useListContext } from "ra-core";

import { Status } from "../misc/Status";
import type { Contact } from "../types";
import { TagsList } from "./TagsList";

export const ContactListContent = () => {
  const { isPending, error } = useListContext<Contact>();

  if (isPending) {
    return <Skeleton className="w-full h-96" />;
  }

  if (error) {
    return null;
  }

  return (
    <DataTable rowClick="show">
      <DataTable.Col
        source="name"
        label="Name"
        render={(contact: Contact) => (
          <div className="font-medium">
            {contact.name ||
              `${contact.first_name || ""} ${contact.last_name || ""}`.trim() ||
              "Unnamed contact"}
          </div>
        )}
      />
      <DataTable.Col
        source="company"
        label="Company"
        render={(contact: Contact) => (
          <TextField source="company" />
        )}
      />
      <DataTable.Col
        source="email"
        label="Email"
        render={(contact: Contact) => (
          <div className="text-sm">{contact.email || "-"}</div>
        )}
      />
      <DataTable.Col
        source="phone"
        label="Phone"
        render={(contact: Contact) => (
          <div className="text-sm">{contact.phone || "-"}</div>
        )}
      />
      <DataTable.Col
        source="contact_type"
        label="Type"
        render={(contact: Contact) => (
          contact.contact_type ? (
            <Badge variant="secondary" className="text-xs font-normal">
              {contact.contact_type}
            </Badge>
          ) : null
        )}
      />
      <DataTable.Col
        source="status"
        label="Status"
        render={(contact: Contact) => (
          <Status status={contact.status} />
        )}
      />
      <DataTable.Col
        source="tags"
        label="Tags"
        disableSort
        render={(contact: Contact) => (
          <div className="flex flex-wrap gap-1">
            <TagsList />
          </div>
        )}
      />
      <DataTable.Col
        source="last_activity"
        label="Last Activity"
        render={(contact: Contact) => {
          const lastActivity = contact.last_activity
            ? new Date(contact.last_activity)
            : contact.created_at
              ? new Date(contact.created_at)
              : undefined;

          if (!lastActivity) return <span className="text-muted-foreground">-</span>;

          return (
            <div className="text-sm text-muted-foreground" title={lastActivity.toISOString()}>
              {formatRelative(lastActivity, Date.now())}
            </div>
          );
        }}
      />
    </DataTable>
  );
};
