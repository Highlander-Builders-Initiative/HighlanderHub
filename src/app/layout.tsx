import type { Metadata } from "next";
import { Analytics } from "@vercel/analytics/next";
import { Bricolage_Grotesque, IBM_Plex_Mono } from "next/font/google";
import {
  SITE_DESCRIPTION,
  SITE_NAME,
  SITE_PREVIEW_IMAGE,
  SITE_TITLE,
  SITE_URL,
} from "@/lib/seo";
import "./globals.css";

const bricolage = Bricolage_Grotesque({
  subsets: ["latin"],
  variable: "--font-bricolage",
  display: "swap",
});

const ibmPlexMono = IBM_Plex_Mono({
  weight: ["400", "500"],
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: SITE_TITLE,
    template: `%s · ${SITE_NAME}`,
  },
  description: SITE_DESCRIPTION,
  applicationName: SITE_NAME,
  manifest: "/manifest.json",
  icons: {
    icon: SITE_PREVIEW_IMAGE,
    apple: SITE_PREVIEW_IMAGE,
  },
  openGraph: {
    type: "website",
    siteName: SITE_NAME,
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    url: "/",
    images: [
      {
        url: SITE_PREVIEW_IMAGE,
        width: 1250,
        height: 1250,
        alt: "Highlander Hub logo",
      },
    ],
  },
  twitter: {
    card: "summary",
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    images: [SITE_PREVIEW_IMAGE],
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${bricolage.variable} ${ibmPlexMono.variable}`}>
      <body>
        {children}
        <Analytics />
      </body>
    </html>
  );
}

