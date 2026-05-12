import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "The Highlander Daily — UCR & Riverside Events",
  description:
    "A bulletin of campus and club events at UC Riverside and around the city of Riverside.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
