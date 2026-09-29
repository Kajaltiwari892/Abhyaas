"use client";

import { Toaster } from "sonner";

export default function AppToaster() {
  return <Toaster position="top-center" closeButton richColors duration={4500} toastOptions={{ className: "abhyaas-toast" }} />;
}
