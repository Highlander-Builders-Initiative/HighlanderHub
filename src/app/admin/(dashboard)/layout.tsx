import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { verifySession } from "@/lib/admin";

interface AdminDashboardLayoutProps {
  children: React.ReactNode;
}

export default async function AdminDashboardLayout({
  children,
}: AdminDashboardLayoutProps) {
  const cookieStore = await cookies();
  const session = cookieStore.get("hh_admin_session")?.value;

  // Server-side redirect to /admin/login if the session is missing, expired, or invalid.
  if (!verifySession(session)) {
    redirect("/admin/login");
  }

  return <>{children}</>;
}
