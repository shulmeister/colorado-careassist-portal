import { useState } from "react";
import { useListContext, useNotify, useRefresh, useDataProvider } from "ra-core";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { Merge } from "lucide-react";

type Contact = {
  id: number;
  first_name?: string;
  last_name?: string;
  name?: string;
  company?: string;
  email?: string;
  phone?: string;
  title?: string;
};

export function BulkMergeButton() {
  const { selectedIds, data, onUnselectItems } = useListContext<Contact>();
  const notify = useNotify();
  const refresh = useRefresh();
  const dataProvider = useDataProvider();
  const [open, setOpen] = useState(false);
  const [primaryId, setPrimaryId] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Only enable merge for 2+ selected items
  const canMerge = selectedIds && selectedIds.length >= 2;

  // Get selected records
  const selectedRecords = data?.filter((c) => selectedIds?.includes(c.id)) || [];

  const handleOpen = () => {
    if (selectedRecords.length > 0) {
      setPrimaryId(selectedRecords[0].id);
    }
    setOpen(true);
  };

  const handleMerge = async () => {
    if (!primaryId || selectedIds.length < 2) return;

    setIsLoading(true);
    try {
      const duplicateIds = selectedIds.filter((id) => id !== primaryId);

      const response = await fetch("api/contacts/merge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          primary_id: primaryId,
          duplicate_ids: duplicateIds,
        }),
      });

      if (response.ok) {
        const result = await response.json();
        notify(`Merged ${result.merged_count} contacts into primary`, { type: "success" });
        onUnselectItems();
        refresh();
        setOpen(false);
      } else {
        const error = await response.json();
        notify(error.detail || "Failed to merge contacts", { type: "error" });
      }
    } catch (error) {
      notify("Failed to merge contacts", { type: "error" });
    } finally {
      setIsLoading(false);
    }
  };

  const getContactName = (contact: Contact) => {
    if (contact.name) return contact.name;
    if (contact.first_name || contact.last_name) {
      return `${contact.first_name || ""} ${contact.last_name || ""}`.trim();
    }
    return contact.email || `Contact #${contact.id}`;
  };

  if (!canMerge) return null;

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        onClick={handleOpen}
        className="gap-2"
      >
        <Merge className="h-4 w-4" />
        Merge
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Merge Contacts</DialogTitle>
            <DialogDescription>
              Select which contact to keep as the primary. All data from other
              contacts will be merged into it, and duplicates will be deleted.
            </DialogDescription>
          </DialogHeader>

          <div className="py-4">
            <Label className="text-sm font-medium mb-3 block">
              Keep as primary:
            </Label>
            <RadioGroup
              value={primaryId?.toString()}
              onValueChange={(val) => setPrimaryId(parseInt(val))}
              className="space-y-3"
            >
              {selectedRecords.map((contact) => (
                <div key={contact.id} className="flex items-start space-x-3">
                  <RadioGroupItem
                    value={contact.id.toString()}
                    id={`contact-${contact.id}`}
                  />
                  <Label
                    htmlFor={`contact-${contact.id}`}
                    className="flex flex-col cursor-pointer"
                  >
                    <span className="font-medium">{getContactName(contact)}</span>
                    <span className="text-xs text-muted-foreground">
                      {[contact.company, contact.title, contact.email, contact.phone]
                        .filter(Boolean)
                        .join(" • ")}
                    </span>
                  </Label>
                </div>
              ))}
            </RadioGroup>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleMerge}
              disabled={!primaryId || isLoading}
            >
              {isLoading ? "Merging..." : `Merge ${selectedIds.length} Contacts`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

