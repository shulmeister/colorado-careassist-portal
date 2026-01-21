import { useRecordContext } from "ra-core";
import { ReferenceArrayField } from "@/components/admin/reference-array-field";
import { SingleFieldList } from "@/components/admin/single-field-list";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Contact } from "../types";

const ColoredBadge = (props: any) => {
  const record = useRecordContext();
  if (!record) return null;
  return (
    <Badge
      {...props}
      style={{ backgroundColor: record.color, border: 0 }}
      variant="outline"
      className={cn("text-black font-normal", props.className)}
    >
      {record.name}
    </Badge>
  );
};

export const TagsList = () => {
  const record = useRecordContext<Contact>();
  if (!record?.tags) {
    return null;
  }

  const tags = Array.isArray(record.tags) ? record.tags : [];
  const areStringTags = tags.every((tag) => typeof tag === "string");

  if (areStringTags) {
    return (
      <div className="inline-flex gap-1 flex-wrap">
        {tags.map((tag) => (
          <Badge
            key={String(tag)}
            variant="secondary"
            className="text-xs font-normal text-black border-0"
          >
            {tag}
          </Badge>
        ))}
      </div>
    );
  }

  return (
    <ReferenceArrayField
      className="inline-block"
      resource="contacts"
      source="tags"
      reference="tags"
    >
      <SingleFieldList>
        <ColoredBadge source="name" />
      </SingleFieldList>
    </ReferenceArrayField>
  );
};
