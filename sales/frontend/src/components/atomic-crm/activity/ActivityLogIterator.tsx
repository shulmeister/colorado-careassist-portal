import { Fragment, useState } from "react";

import { Separator } from "@/components/ui/separator";
import {
  COMPANY_CREATED,
  CONTACT_CREATED,
  CONTACT_NOTE_CREATED,
  DEAL_CREATED,
  DEAL_NOTE_CREATED,
} from "../consts";
import type { Activity } from "../types";
import { ActivityLogCompanyCreated } from "./ActivityLogCompanyCreated";
import { ActivityLogContactCreated } from "./ActivityLogContactCreated";
import { ActivityLogContactNoteCreated } from "./ActivityLogContactNoteCreated";
import { ActivityLogDealCreated } from "./ActivityLogDealCreated";
import { ActivityLogDealNoteCreated } from "./ActivityLogDealNoteCreated";

type ActivityLogIteratorProps = {
  activities: Activity[];
  pageSize: number;
};

export function ActivityLogIterator({
  activities,
  pageSize,
}: ActivityLogIteratorProps) {
  const [activitiesDisplayed, setActivityDisplayed] = useState(pageSize);

  // Defensive check: ensure activities is an array
  if (!activities || !Array.isArray(activities)) {
    return null;
  }

  const filteredActivities = activities.slice(0, activitiesDisplayed);

  return (
    <div className="space-y-4">
      {filteredActivities.map((activity, index) => (
        <Fragment key={index}>
          <ActivityItem key={activity.id} activity={activity} />
          <Separator />
        </Fragment>
      ))}

      {activitiesDisplayed < activities.length && (
        <a
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setActivityDisplayed(
              (activitiesDisplayed) => activitiesDisplayed + pageSize,
            );
          }}
          className="flex w-full justify-center text-sm underline hover:no-underline"
        >
          Load more activity
        </a>
      )}
    </div>
  );
}

function ActivityItem({ activity }: { activity: Activity }) {
  if (activity.type === COMPANY_CREATED) {
    return <ActivityLogCompanyCreated activity={activity} />;
  }

  if (activity.type === CONTACT_CREATED) {
    return <ActivityLogContactCreated activity={activity} />;
  }

  if (activity.type === CONTACT_NOTE_CREATED) {
    return <ActivityLogContactNoteCreated activity={activity} />;
  }

  if (activity.type === DEAL_CREATED) {
    return <ActivityLogDealCreated activity={activity} />;
  }

  if (activity.type === DEAL_NOTE_CREATED) {
    return <ActivityLogDealNoteCreated activity={activity} />;
  }

  // Fallback: Render generic activity (visits, calls, emails, scans, etc.)
  return <ActivityLogGeneric activity={activity} />;
}

// Generic activity log item for any activity type
function ActivityLogGeneric({ activity }: { activity: Activity }) {
  const getActivityIcon = (type: string) => {
    switch(type) {
      case 'visit': return '🚗';
      case 'call': return '📞';
      case 'email': return '📧';
      case 'scan': return '📄';
      case 'business_card_scanned': return '💼';
      case 'note': return '📝';
      default: return '📌';
    }
  };

  return (
    <div className="flex items-start space-x-3">
      <div className="text-2xl">{getActivityIcon(activity.type)}</div>
      <div className="flex-1">
        <div className="text-sm font-medium text-foreground">
          {activity.name || 'Activity'}
        </div>
        {activity.preview_url && (
          <div className="text-xs text-muted-foreground mt-1">
            {new Date(activity.preview_url).toLocaleDateString()}
          </div>
        )}
      </div>
    </div>
  );
}
