import { formatRelative } from "date-fns";
import { RecordContextProvider, useListContext } from "ra-core";
import { type MouseEvent, useCallback } from "react";
import { Link } from "react-router";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { useIsMobile } from "@/hooks/use-mobile";
import { Badge } from "@/components/ui/badge";

import { Status } from "../misc/Status";
import type { Contact } from "../types";
import { Avatar } from "./Avatar";
import { TagsList } from "./TagsList";

export const ContactListContent = () => {
  const {
    data: contacts,
    error,
    isPending,
    onToggleItem,
    selectedIds,
  } = useListContext<Contact>();
  const isSmall = useIsMobile();

  // StopPropagation does not work for some reason on Checkbox, this handler is a workaround
  const handleLinkClick = useCallback(function handleLinkClick(
    e: MouseEvent<HTMLAnchorElement>,
  ) {
    if (e.target instanceof HTMLButtonElement) {
      e.preventDefault();
    }
  }, []);

  if (isPending) {
    return <Skeleton className="w-full h-9" />;
  }

  if (error) {
    return null;
  }
  const now = Date.now();

  return (
    <div className="divide-y">
      {contacts.map((contact) => {
        const lastActivity = contact.last_activity
          ? new Date(contact.last_activity)
          : contact.created_at
            ? new Date(contact.created_at)
            : undefined;

        return (
          <RecordContextProvider key={contact.id} value={contact}>
            <Link
              to={`/contacts/${contact.id}/show`}
              className="flex flex-row gap-4 items-center px-4 py-2 hover:bg-muted transition-colors first:rounded-t-xl last:rounded-b-xl"
              onClick={handleLinkClick}
            >
            <Checkbox
              className="cursor-pointer"
              checked={selectedIds.includes(contact.id)}
              onCheckedChange={() => onToggleItem(contact.id)}
            />
            <Avatar />
            <div className="flex-1 min-w-0">
              <div className="font-medium">
                {contact.name ||
                  `${contact.first_name || ""} ${contact.last_name || ""}`.trim() ||
                  "Unnamed contact"}
              </div>
              <div className="text-sm text-muted-foreground flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-2">
                <span className="truncate">
                  {[contact.company, contact.email, contact.phone]
                    .filter(Boolean)
                    .join(" • ")}
                </span>
                <div className="flex flex-wrap gap-1 items-center">
                  {contact.contact_type && (
                    <Badge variant="secondary" className="text-xs font-normal">
                      {contact.contact_type}
                    </Badge>
                  )}
                  <TagsList />
                </div>
              </div>
            </div>
            {lastActivity && (
              <div className="text-right ml-4">
                <div
                  className="text-sm text-muted-foreground"
                  title={lastActivity.toISOString()}
                >
                  {!isSmall && "last activity "}
                  {formatRelative(lastActivity, now)}{" "}
                  <Status status={contact.status} />
                </div>
              </div>
            )}
          </Link>
          </RecordContextProvider>
        );
      })}

      {contacts.length === 0 && (
        <div className="p-4">
          <div className="text-muted-foreground">No contacts found</div>
        </div>
      )}
    </div>
  );
};
