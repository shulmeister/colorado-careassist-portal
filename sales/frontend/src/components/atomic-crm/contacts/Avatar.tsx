import {
  AvatarFallback,
  AvatarImage,
  Avatar as ShadcnAvatar,
} from "@/components/ui/avatar";
import { useRecordContext } from "ra-core";

import type { Contact } from "../types";

export const Avatar = (props: {
  record?: Contact;
  width?: 20 | 25 | 40;
  height?: 20 | 25 | 40;
  title?: string;
}) => {
  const record = useRecordContext<Contact>(props);
  const displayName =
    record?.name ||
    `${record?.first_name || ""} ${record?.last_name || ""}`.trim();

  if (!record?.avatar && !displayName) {
    return null;
  }

  const size = props.width || props.height;
  const sizeClass =
    props.width === 20
      ? `w-[20px] h-[20px]`
      : props.width === 25
        ? "w-[25px] h-[25px]"
        : "w-10 h-10";

  return (
    <ShadcnAvatar className={sizeClass} title={props.title}>
      <AvatarImage src={record.avatar?.src ?? undefined} />
      <AvatarFallback className={size && size < 40 ? "text-[10px]" : "text-sm"}>
        {displayName
          ?.split(" ")
          .filter(Boolean)
          .slice(0, 2)
          .map((part) => part.charAt(0).toUpperCase())
          .join("")}
      </AvatarFallback>
    </ShadcnAvatar>
  );
};
