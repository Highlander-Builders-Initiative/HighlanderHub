import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Highlander Hub — UCR & Riverside Events",
  description:
    "Campus and club events at UC Riverside and around the city — in one clean feed.",
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
