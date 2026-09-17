import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "MateERP",
  description: "Enterprise financial and business operations ERP by NetaMate Solutions",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
