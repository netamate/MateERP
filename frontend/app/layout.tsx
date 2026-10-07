import type { Metadata } from "next";

import { QueryProvider } from "@/components/providers/query-provider";

import "./globals.css";

export const metadata: Metadata = {
  applicationName: "MateERP",
  title: {
    default: "MateERP",
    template: "%s | MateERP",
  },
  description: "Internal business, subscription and renewal management",
  icons: {
    icon: [{ url: "/images/favicon.png", sizes: "128x128", type: "image/png" }],
    shortcut: "/images/favicon.png",
    apple: "/images/favicon.png",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
