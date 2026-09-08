import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CareerMatrix | AI-Powered Career Intelligence & Decision System",
  description: "AI-Powered Career Intelligence & Decision System",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
