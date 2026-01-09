import { useGetIdentity, useGetList } from "ra-core";

export const TasksListEmpty = () => {
  // Support both react-admin identity hook shapes ({ data } vs { identity })
  const identityResult = useGetIdentity() as any;
  const identity = identityResult?.identity ?? identityResult?.data;

  const { total } = useGetList(
    "tasks",
    {
      pagination: { page: 1, perPage: 1 },
      filter: {
        sales_id: identity?.id,
        assigned_to: identity?.email ?? identity?.id,
      },
    },
    { enabled: !!identity },
  );

  if (total) return null;

  return (
    <p className="text-sm">Tasks added to your contacts will appear here.</p>
  );
};
