import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ZeroMinute IR",
  description: "Code-aware emergency incident runbooks for verified contracts",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-mono antialiased">{children}</body>
    </html>
  );
}
