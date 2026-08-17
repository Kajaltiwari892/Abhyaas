import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import MotionLayer from "./components/MotionLayer";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Abhyaas — Free CDS Preparation",
  description: "Daily CDS practice, NCERT-based learning, previous year papers and source-grounded doubt solving in one free platform.",
};

export const viewport = {
  themeColor: "#123c31",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col"><MotionLayer>{children}</MotionLayer></body>
    </html>
  );
}
