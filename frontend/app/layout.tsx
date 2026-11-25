import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AlertBanner } from "@/components/alerts/AlertBanner";
import { AlertNotifier } from "@/components/alerts/AlertNotifier";
import { Sidebar } from "@/components/layout/Sidebar";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Plataforma de Inteligência Climática", template: "%s · Inteligência Climática" },
  description:
    "Monitoramento meteorológico, análise geoespacial e estimativa de condições favoráveis a alagamentos.",
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
            <aside className="border-b border-surface-border bg-surface md:w-60 md:shrink-0 md:border-b-0 md:border-r">
              <Sidebar />
            </aside>
            <div className="flex min-w-0 flex-1 flex-col">
              <AlertBanner />
              <main id="conteudo" className="min-w-0 flex-1 p-4 md:p-8">
                {children}
              </main>
            </div>
          </div>
          <AlertNotifier />
        </Providers>
      </body>
    </html>
  );
}
