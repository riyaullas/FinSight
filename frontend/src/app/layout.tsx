import type { Metadata, Viewport } from "next";
import { AuthProvider } from "@/lib/auth";
import { PRODUCT_NAME } from "@/lib/brand";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: PRODUCT_NAME, template: `%s · ${PRODUCT_NAME}` },
  description: "Business operating system — finance, CRM, risk and analytics on your own infrastructure.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

// Applies the saved theme before first paint to avoid a flash of the wrong theme.
const themeScript = `(()=>{try{const t=localStorage.getItem("theme");const d=t?t==="dark":matchMedia("(prefers-color-scheme: dark)").matches;document.documentElement.classList.toggle("dark",d)}catch(e){}})()`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
