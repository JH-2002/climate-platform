// Provedores de mapa (fundo e relevo). Um lugar só para os componentes e para a CSP
// (spec 011, BR-171): o que o mapa carrega precisa estar liberado nos cabeçalhos.

export const DEFAULT_MAP_STYLE_URL = "https://tiles.openfreemap.org/styles/liberty";
export const DEFAULT_TERRAIN_TILES_URL =
  "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png";

/**
 * URLs que o mapa vai usar, com os padrões quando a variável não foi definida.
 * @param {{ style?: string, terrain?: string }} env
 * @returns {string[]}
 */
export function mapSourceUrls({ style, terrain }) {
  return [style || DEFAULT_MAP_STYLE_URL, terrain || DEFAULT_TERRAIN_TILES_URL];
}
