export const TEAM_ASSIGNEES: Array<{ email: string; name: string }> = [
  { email: "jacob@coloradocareassist.com", name: "Jacob" },
  { email: "cynthia@coloradocareassist.com", name: "Cynthia" },
  { email: "jason@coloradocareassist.com", name: "Jason" },
];

export function getAssigneeLabel(email?: string | null, meEmail?: string | null) {
  if (!email) return "";
  if (meEmail && email === meEmail) return "Me";
  const found = TEAM_ASSIGNEES.find((a) => a.email === email);
  return found?.name ?? email;
}

export function getAssigneeChoices(meEmail?: string | null) {
  const choices: Array<{ id: string; name: string }> = [];

  if (meEmail) {
    choices.push({ id: meEmail, name: "Me" });
  }

  for (const a of TEAM_ASSIGNEES) {
    // Avoid duplicates when "me" is Jacob/Maryssa
    if (a.email === meEmail) continue;
    choices.push({ id: a.email, name: a.name });
  }

  return choices;
}





