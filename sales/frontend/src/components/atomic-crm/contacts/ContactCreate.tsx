import { CreateBase, Form, useGetIdentity } from "ra-core";
import { FormToolbar } from "@/components/admin/simple-form";
import { Card, CardContent } from "@/components/ui/card";

import type { Contact } from "../types";
import { ContactInputs } from "./ContactInputs";

export const ContactCreate = () => {
  const { identity } = useGetIdentity();
  return (
    <CreateBase
      redirect="show"
      transform={(data: Contact) => ({
        ...data,
        created_at: new Date().toISOString(),
        last_activity: new Date().toISOString(),
        tags: data.tags || [],
      })}
    >
      <div className="mt-2 flex lg:mr-72">
        <div className="flex-1">
          <Form defaultValues={{ sales_id: identity?.id }}>
            <Card>
              <CardContent>
                <ContactInputs />
                <FormToolbar />
              </CardContent>
            </Card>
          </Form>
        </div>
      </div>
    </CreateBase>
  );
};
