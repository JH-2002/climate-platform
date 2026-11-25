import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { AlertBanner } from "@/components/alerts/AlertBanner";
import { AlertNotifier } from "@/components/alerts/AlertNotifier";
import { DemoBanner } from "@/components/layout/DemoBanner";
import { OfflineBanner } from "@/components/layout/OfflineBanner";
import { PwaRegister } from "@/components/layout/PwaRegister";
import { Sidebar } from "@/components/layout/Sidebar";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Plataforma de Inteligência Climática", template: "%s · Inteligência Climática" },
  description:
    "Monitoramento meteorológico, análise geoespacial e estimativa de condições favoráveis a alagamentos.",
  // Caminhos relativos ao basePath do Next (vitrine no GitHub Pages) — spec 013, FR-202.
  manifest: `${process.env.NEXT_PUBLIC_BASE_PATH ?? ""}/manifest.webmanifest`,
  icons: {
    icon: `${process.env.NEXT_PUBLIC_BASE_PATH ?? ""}/icons/icon-192.png`,
    apple: `${process.env.NEXT_PUBLIC_BASE_PATH ?? ""}/icons/apple-touch-icon.png`,
  },
  appleWebApp: { capable: true, title: "Clima SP", statusBarStyle: "default" },
};

export const viewport: Viewport = {
  themeColor: "#0b5c7a",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>
        <a
          href="#conteudo"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2"
        >
          Pular para o conteúdo
        </a>
        <Providers>
          <div className="flex min-h-screen flex-col md:flex-row">
            <aside className="sticky top-0 z-30 border-b border-surface-border bg-surface md:static md:w-60 md:shrink-0 md:border-b-0 md:border-r">
              <Sidebar />
            </aside>
            <div className="flex min-w-0 flex-1 flex-col">
              <OfflineBanner />
              <DemoBanner />
              <AlertBanner />
              <main id="conteudo" className="min-w-0 flex-1 p-4 md:p-8">
                {children}
              </main>
            </div>
          </div>
          <AlertNotifier />
          <PwaRegister />
        </Providers>
      </body>
    </html>
  );
}
