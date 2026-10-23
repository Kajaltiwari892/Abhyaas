import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import MotionLayer from "./components/MotionLayer";
import AuthProvider from "./components/AuthProvider";
import AppToaster from "./components/AppToaster";
import QueryProvider from "./components/QueryProvider";

// Bundle the same Latin font files as production. A failed Google Fonts download
// in development otherwise substitutes enlarged Arial for the compact labels.
const geistSans = localFont({
  src: "./fonts/geist-latin-variable.woff2",
  variable: "--font-geist-sans",
  weight: "100 900",
  style: "normal",
  display: "swap",
  fallback: ["Arial", "sans-serif"],
  adjustFontFallback: false,
});

const geistMono = localFont({
  src: "./fonts/geist-mono-latin-variable.woff2",
  variable: "--font-geist-mono",
  weight: "100 900",
  style: "normal",
  display: "swap",
  fallback: ["ui-monospace", "Consolas", "monospace"],
  adjustFontFallback: false,
});

export const metadata: Metadata = {
  referrer: "no-referrer",
  title: "Abhyaas — Free CDS Preparation",
  description: "Daily CDS practice, NCERT-based learning, previous year papers and source-grounded doubt solving in one free platform.",
};

export const viewport = {
  themeColor: "#10170e",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      data-theme="dark"
      data-scroll-behavior="smooth"
      style={{ colorScheme: "dark" }}
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col"><QueryProvider><AuthProvider><MotionLayer>{children}</MotionLayer><AppToaster /></AuthProvider></QueryProvider></body>
    </html>
  );
}
