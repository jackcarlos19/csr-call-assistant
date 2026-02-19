import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CSR Call Assistant",
  description: "Real-time agent assist for home services",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-950 text-slate-100">{children}</body>
    </html>
  );
}
