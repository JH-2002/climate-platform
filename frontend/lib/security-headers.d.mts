export function originOf(url: string | undefined | null): string | null;
export function securityHeaders(options: {
  dev: boolean;
  mapUrls: (string | undefined)[];
}): { key: string; value: string }[];
