import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import MotionLayer from "./components/MotionLayer";
import AuthProvider from "./components/AuthProvider";
import AppToaster from "./components/AppToaster";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
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
      <body className="min-h-full flex flex-col"><AuthProvider><MotionLayer>{children}</MotionLayer><AppToaster /></AuthProvider></body>
    </html>
  );
}
