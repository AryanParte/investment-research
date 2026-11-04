import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Investment Research · Private Pilot",
  description: "Synthetic research dashboard. Recommendation only; no financial connections.",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
