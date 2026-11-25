import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";

/** Render com React Query, sem novas tentativas; os dados entram por `seed` (sem rede). */
export function renderWithQuery(ui: ReactElement, seed: [unknown[], unknown][] = []) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  for (const [key, data] of seed) client.setQueryData(key, data);
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}
