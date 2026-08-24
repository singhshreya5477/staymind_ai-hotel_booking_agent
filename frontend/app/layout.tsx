import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "StayMind AI", description: "Hotel booking agent" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}