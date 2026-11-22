/**
 * layout.tsx — wraps EVERY page. It loads the fonts, sets the page title,
 * turns on toast messages, and adds the sidebar frame (Shell).
 */
import type { Metadata, Viewport } from "next";
import { AuthProvider } from "@/components/AuthProvider";
import { Shell } from "@/components/Shell";
import { ToastProvider } from "@/components/Toast";
import "./globals.css";

export const metadata: Metadata = {
  title: "TalentIQ — Blind, evidence-led hiring",
  description: "Hide identity, quote the proof, score with plain maths. You make every hiring decision.",
};

export const viewport: Viewport = { themeColor: "#0e1726" };

// Fonts: Bricolage Grotesque for the interface, Newsreader for résumé text.
const FONTS =
  "https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400..800&family=Newsreader:ital,opsz,wght@0,6..72,400..600;1,6..72,400..600&display=swap";

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link rel="stylesheet" href={FONTS} />
      </head>
      <body>
        <ToastProvider>
          <AuthProvider>
            <Shell>{children}</Shell>
          </AuthProvider>
        </ToastProvider>
      </body>
    </html>
  );
}
