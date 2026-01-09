import type { ConfigurationContextValue } from "../root/ConfigurationContext";
import type { Deal } from "../types";

export type DealsByStage = Record<Deal["stage"], Deal[]>;

export const getDealsByStage = (
  unorderedDeals: Deal[],
  dealStages: ConfigurationContextValue["dealStages"],
) => {
  if (!dealStages) return {};
  const dealsByStage: Record<Deal["stage"], Deal[]> = unorderedDeals.reduce(
    (acc, deal) => {
      // Handle deals with unknown stages gracefully - put them in the first stage
      const stage = acc[deal.stage] ? deal.stage : dealStages[0]?.value;
      if (stage && acc[stage]) {
        acc[stage].push(deal);
      }
      return acc;
    },
    dealStages.reduce(
      (obj, stage) => ({ ...obj, [stage.value]: [] }),
      {} as Record<Deal["stage"], Deal[]>,
    ),
  );
  // order each column by index
  dealStages.forEach((stage) => {
    dealsByStage[stage.value] = dealsByStage[stage.value].sort(
      (recordA: Deal, recordB: Deal) => (recordA.index ?? 0) - (recordB.index ?? 0),
    );
  });
  return dealsByStage;
};
