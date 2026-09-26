import type { Metadata } from "next";

// Metadata only: the login page is a client component and can't export it.
export const metadata: Metadata = {
  title: "Admin",
  robots: { index: false, follow: false },
};

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return children;
}
