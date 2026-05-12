import type { Metadata } from "next";
import { AuthProvider } from "@/components/auth-provider";
import { ToastProvider } from "@/components/toast-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Multi-Agent Research Knowledge Assistant",
  description: "Modern AI dashboard for document QA with a multi-agent RAG pipeline."
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (() => {
                document.documentElement.classList.add("dark");
                document.documentElement.dataset.theme = "dark";
                localStorage.setItem("theme", "dark");
              })();
            `
          }}
        />
      </head>
      <body>
        <ToastProvider>
          <AuthProvider>{children}</AuthProvider>
        </ToastProvider>
      </body>
    </html>
  );
}
