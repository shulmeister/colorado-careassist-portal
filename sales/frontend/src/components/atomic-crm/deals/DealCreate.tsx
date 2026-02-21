import { useState, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  Form,
  useDataProvider,
  useGetIdentity,
  useListContext,
  useRedirect,
  useNotify,
  type GetListResult,
} from "ra-core";
import { Create } from "@/components/admin/create";
import { SaveButton } from "@/components/admin/form";
import { FormToolbar } from "@/components/admin/simple-form";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { FileUp } from "lucide-react";

import type { Deal } from "../types";
import { DealInputs } from "./DealInputs";

export const DealCreate = ({ open }: { open: boolean }) => {
  const redirect = useRedirect();
  const dataProvider = useDataProvider();
  const { data: allDeals } = useListContext<Deal>();

  const handleClose = () => {
    redirect("/deals");
  };

  const queryClient = useQueryClient();

  const onSuccess = async (deal: Deal) => {
    if (!allDeals) {
      redirect("/deals");
      return;
    }
    // increase the index of all deals in the same stage as the new deal
    // first, get the list of deals in the same stage
    const deals = allDeals.filter(
      (d: Deal) => d.stage === deal.stage && d.id !== deal.id,
    );
    // update the actual deals in the database
    await Promise.all(
      deals.map(async (oldDeal) =>
        dataProvider.update("deals", {
          id: oldDeal.id,
          data: { index: oldDeal.index + 1 },
          previousData: oldDeal,
        }),
      ),
    );
    // refresh the list of deals in the cache as we used dataProvider.update(),
    // which does not update the cache
    const dealsById = deals.reduce(
      (acc, d) => ({
        ...acc,
        [d.id]: { ...d, index: d.index + 1 },
      }),
      {} as { [key: string]: Deal },
    );
    const now = Date.now();
    queryClient.setQueriesData<GetListResult | undefined>(
      { queryKey: ["deals", "getList"] },
      (res) => {
        if (!res) return res;
        return {
          ...res,
          data: res.data.map((d: Deal) => dealsById[d.id] || d),
        };
      },
      { updatedAt: now },
    );
    redirect("/deals");
  };

  const { identity } = useGetIdentity();
  const notify = useNotify();
  const [scanning, setScanning] = useState(false);
  const [prefill, setPrefill] = useState<Record<string, string>>({});
  const fileRef = useRef<HTMLInputElement>(null);

  const handleScanFaceSheet = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setScanning(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const resp = await fetch("/api/parse-va-rfs-referral", {
        method: "POST",
        body: formData,
        credentials: "include",
      });
      const data = await resp.json();
      if (data.success !== false && data.veteran_first_name) {
        const name = `${data.veteran_first_name || ""} ${data.veteran_last_name || ""}`.trim();
        const desc = [
          data.diagnosis_primary && `Dx: ${data.diagnosis_primary}`,
          data.facility_name && `Facility: ${data.facility_name}`,
          data.service_requested && `Service: ${data.service_requested}`,
          data.medications && `Meds: ${data.medications}`,
          data.allergies && `Allergies: ${data.allergies}`,
        ].filter(Boolean).join("\n");

        setPrefill({ name, description: desc, phone: data.phone || "", city: data.city || "" });

        // Auto-create contact + deal via backend
        const createResp = await fetch("/sales/api/deals/create-from-facesheet", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            first_name: data.veteran_first_name,
            last_name: data.veteran_last_name,
            phone: data.phone,
            address: data.address,
            city: data.city,
            state: data.state,
            zip: data.zip,
            diagnosis: data.diagnosis_primary,
            facility: data.facility_name,
            description: desc,
          }),
        });
        const result = await createResp.json();
        if (result.deal_id) {
          notify(`Created deal for ${name}`, { type: "success" });
          redirect("/deals");
        } else {
          notify(result.error || "Created contact but deal creation failed", { type: "warning" });
        }
      } else {
        notify("Could not extract data from PDF. Try a clearer scan.", { type: "error" });
      }
    } catch (err) {
      notify("Face sheet scan failed", { type: "error" });
    } finally {
      setScanning(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <Dialog open={open} onOpenChange={() => handleClose()}>
      <DialogContent className="lg:max-w-4xl overflow-y-auto max-h-9/10 top-1/20 translate-y-0">
        {/* Face Sheet Scanner */}
        <div className="border border-dashed border-primary/30 rounded-lg p-3 mb-2 bg-primary/5">
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              className="flex items-center gap-2 text-primary border-primary/30"
              onClick={() => fileRef.current?.click()}
              disabled={scanning}
            >
              <FileUp className="w-4 h-4" />
              {scanning ? "Scanning..." : "Scan Face Sheet / Referral"}
            </Button>
            <span className="text-xs text-muted-foreground">
              Upload a referral PDF to auto-create deal + contact
            </span>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={handleScanFaceSheet}
            />
          </div>
        </div>

        <Create resource="deals" mutationOptions={{ onSuccess }}>
          <Form
            defaultValues={{
              sales_id: identity?.id,
              contact_ids: [],
              index: 0,
              name: prefill.name || "",
              description: prefill.description || "",
            }}
          >
            <DealInputs />
            <FormToolbar>
              <SaveButton />
            </FormToolbar>
          </Form>
        </Create>
      </DialogContent>
    </Dialog>
  );
};
