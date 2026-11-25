import Link from "next/link";
import { reportHref } from "@/features/reports/form";
import type { ReportType } from "@/features/reports/types";

/** Atalho "Gerar relatório" nas outras páginas (FR-156). */
export function ReportShortcut({ type, params = {}, label = "Gerar relatório" }: { type: ReportType; params?: Record<string, string>; label?: string }) {
  return (
    <Link href={reportHref(type, params)} className="inline-flex items-center gap-1 rounded-md border border-accent px-3 py-1.5 text-sm font-medium text-accent hover:bg-accent hover:text-white">
      <span aria-hidden="true">⇩</span>
      {label}
    </Link>
  );
}
