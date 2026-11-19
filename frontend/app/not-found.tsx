import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-xl space-y-3 py-12">
      <h1 className="text-2xl font-semibold">Página não encontrada</h1>
      <p className="text-sm text-ink-muted">
        Este endereço não existe ou o módulo ainda não foi implementado.
      </p>
      <Link href="/" className="text-sm font-medium text-accent underline">
        Voltar ao Overview
      </Link>
    </div>
  );
}
