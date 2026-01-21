export const SERVICE_AREAS = [
  "Denver",
  "Boulder",
  "Pueblo",
  "El Paso",
  "Douglas",
  "Jefferson",
  "Adams",
  "Broomfield",
  "Arapahoe",
];

export const REFERRAL_CATEGORIES = [
  {
    label: "Medical Providers",
    types: [
      // Match current production DB values (ReferralSource.source_type)
      "Hospital / Transitions",
      "Skilled Nursing",
      "Primary Care",
    ],
  },
  {
    label: "Senior Living",
    // Match current production DB values
    types: ["Senior Living", "Senior Housing"],
  },
  {
    label: "Legal & Financial",
    // Match current production DB values
    types: ["Legal / Guardianship", "Payer / Insurance"],
  },
  {
    label: "Community & Nonprofit",
    // Match current production DB values
    types: ["Community Organization"],
  },
  {
    label: "Service Providers",
    // Match current production DB values
    types: ["Home Care Partner", "Placement Agency", "Healthcare Facility"],
  },
] as const;

export const REFERRAL_TYPES = REFERRAL_CATEGORIES.flatMap((category) => category.types);
