import {
  ListContextProvider,
  ResourceContextProvider,
  useGetIdentity,
  useGetList,
  useList,
} from "ra-core";

import { TasksIterator } from "../tasks/TasksIterator";

export const TasksListFilter = ({
  title,
  filter,
}: {
  title: string;
  filter: any;
}) => {
  // react-admin v5 returns { data }, but some older codepaths used { identity }.
  // Support both shapes to avoid silently disabling queries.
  const identityResult = useGetIdentity() as any;
  const identity = identityResult?.identity ?? identityResult?.data;

  const {
    data: tasks,
    total,
    isPending,
  } = useGetList(
    "tasks",
    {
      pagination: { page: 1, perPage: 100 },
      sort: { field: "due_date", order: "ASC" },
      filter: {
        ...filter,
        // Backward compat: backend treats sales_id as assignee for the tasks resource.
        sales_id: identity?.id,
        assigned_to: identity?.email ?? identity?.id,
      },
    },
    { enabled: !!identity },
  );

  const listContext = useList({
    data: tasks,
    isPending,
    resource: "tasks",
    perPage: 5,
  });

  // If there are no tasks for this bucket, hide the bucket (the parent shows an empty state).
  if (isPending || !tasks || !total) return null;

  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs uppercase tracking-wider text-muted-foreground font-medium mb-2">
        {title}
      </p>
      <ResourceContextProvider value="tasks">
        <ListContextProvider value={listContext}>
          <TasksIterator showContact />
        </ListContextProvider>
      </ResourceContextProvider>
      {total > listContext.perPage && (
        <div className="flex justify-center">
          <a
            href="#"
            onClick={(e) => {
              listContext.setPerPage(listContext.perPage + 10);
              e.preventDefault();
            }}
            className="text-sm underline hover:no-underline"
          >
            Load more
          </a>
        </div>
      )}
    </div>
  );
};
