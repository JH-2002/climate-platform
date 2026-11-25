export const DEFAULT_MAP_STYLE_URL: string;
export const DEFAULT_TERRAIN_TILES_URL: string;
export function mapSourceUrls(env: { style?: string; terrain?: string }): string[];
