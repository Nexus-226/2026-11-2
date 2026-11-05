export type IconName =
  | "chat"
  | "records"
  | "reminders"
  | "mine"
  | "pets"
  | "nearby"
  | "lost"
  | "vlogs"
  | "chevron"
  | "vaccine"
  | "deworming"
  | "bath"
  | "weight";
export default function AppIcon({ name }: { name: IconName }) {
  const paths: Record<IconName, string> = {
    vaccine: "m15 3 6 6M13 5l6 6M4 15l5 5 10-10-5-5ZM3 21l4-4M10 9l5 5",
    deworming: "M12 3 3 7v5c0 5 9 9 9 9s9-4 9-9V7ZM8 12l3 3 5-6",
    bath: "M5 12h14v3a6 6 0 0 1-6 6h-2a6 6 0 0 1-6-6ZM3 12h18M7 12V6a3 3 0 0 1 6 0M13 6h3M8 21v1M16 21v1",
    weight:
      "M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2M7 7a7 7 0 0 1 10 0l-5 5ZM12 7v4",
    chat: "M4 4h16v13H9l-5 4V4ZM8 9h8M8 13h5",
    records: "M8 4H5v17h14V4h-3M9 2h6v4H9ZM8 11h8M8 16h5",
    reminders: "M18 8a6 6 0 0 0-12 0c0 6-3 7-3 9h18c0-2-3-3-3-9M10 21h4",
    mine: "M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0M4 21v-3a8 8 0 0 1 16 0v3",
    pets: "M5 3h12a2 2 0 0 1 2 2v16H7a3 3 0 0 1-3-3V5a2 2 0 0 1 2-2M4 17h15M9 7h5M9 11h3",
    nearby:
      "M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0ZM15 10a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z",
    lost: "M11 21H4V3h13v7M7 7h7M7 11h3M21 16a5 5 0 1 1-10 0 5 5 0 0 1 10 0ZM20 20l3 3",
    vlogs:
      "M4 8h4l2-3h4l2 3h4v12H4V8ZM12 17a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z",
    chevron: "m6 9 6 6 6-6",
  };
  return (
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={name === "chevron" ? 2 : 1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name]} />
    </svg>
  );
}
