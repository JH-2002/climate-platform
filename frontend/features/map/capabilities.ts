/** Detecção de WebGL (FR-058). Sem WebGL, a página mostra só a lista. */
export function supportsWebGL(doc: Document = document): boolean {
  try {
    const canvas = doc.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") ?? canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

export function prefersReducedMotion(win: Window = window): boolean {
  return Boolean(win.matchMedia?.("(prefers-reduced-motion: reduce)").matches);
}
