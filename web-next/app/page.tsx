import { redirect } from "next/navigation";

// This POC only implements one page (see docs/FRONTEND_ROADMAP.md, Stage
// 2) — send the bare root straight there instead of leaving the default
// create-next-app landing page.
export default function RootPage() {
  redirect("/history");
}
