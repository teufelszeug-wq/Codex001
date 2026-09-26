import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Creative Consistency OS",
  description: "World building, story bible, continuity and writing workspace",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
