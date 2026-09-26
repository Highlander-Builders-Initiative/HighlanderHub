import type { Metadata, Viewport } from "next";
import { Analytics } from "@vercel/analytics/next";
import { Bricolage_Grotesque } from "next/font/google";
import {
  SITE_DESCRIPTION,
  SITE_NAME,
  SITE_SOCIAL_CARD,
  SITE_TITLE,
  SITE_URL,
} from "@/lib/seo";
import { EventsNavSkeleton } from "@/components/events/EventsNavSkeleton";
import "./globals.css";

const bricolage = Bricolage_Grotesque({
  subsets: ["latin"],
  variable: "--font-bricolage",
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
  // Sized cuts of public/logo_icon.png (1250px) so tabs don't pull the full PNG.
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "48x48" },
      { url: "/icon-192.png", type: "image/png", sizes: "192x192" },
    ],
    apple: "/apple-touch-icon.png",
  },
  openGraph: {
    type: "website",
    siteName: SITE_NAME,
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    url: "/",
    images: [SITE_SOCIAL_CARD],
  },
  twitter: {
    card: "summary_large_image",
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    images: [SITE_SOCIAL_CARD.url],
  },
};

// Browser chrome (the iOS status bar, Android's toolbar) matches the page,
// following the device's light/dark setting like the palette does.
export const viewport: Viewport = {
  colorScheme: "light dark",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#1e1f22" },
  ],
};

export default function RootLayout({
  children,
  modal,
}: {
  children: React.ReactNode;
  /** @modal slot: event detail as an overlay when opened from a card. */
  modal: React.ReactNode;
}) {
  return (
    <html lang="en" className={bricolage.variable}>
      <body>
        {children}
        {modal}
        <EventsNavSkeleton />
        <Analytics />
      </body>
    </html>
  );
}

