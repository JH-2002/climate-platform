import { describe, expect, it } from "vitest";
import { resolveSelectedLocation } from "@/features/locations/selection";
import {
  INITIAL_STATE,
  PRESET_LOCATION,
  STORAGE_KEY,
  addLocation,
  loadLocations,
  removeLocation,
  saveLocations,
  setDefaultLocation,
  validateLocation,
  type StorageLike,
} from "@/features/locations/store";

function memoryStorage(initial: Record<string, string> = {}): StorageLike & { data: Record<string, string> } {
  const data = { ...initial };
  return {
    data,
    getItem: (k) => data[k] ?? null,
    setItem: (k, v) => {
      data[k] = v;
    },
  };
}

describe("locais salvos (AC-043, ADR-008)", () => {
  it("adiciona, persiste, recarrega e remove", () => {
    const storage = memoryStorage();
    let state = addLocation(INITIAL_STATE, { name: " Casa ", lat: -23.6, lon: -46.7 }, () => "casa");
    expect(saveLocations(storage, state)).toBe(true);

    const reloaded = loadLocations(storage);
    expect(reloaded.locations.map((l) => l.name)).toEqual(["Centro de São Paulo", "Casa"]);

    state = removeLocation(reloaded, "casa");
    saveLocations(storage, state);
    expect(loadLocations(storage).locations).toEqual([PRESET_LOCATION]);
  });

  it("o local padrão volta para o preset quando o padrão é removido", () => {
    let state = addLocation(INITIAL_STATE, { name: "Trabalho", lat: -23.5, lon: -46.6 }, () => "t");
    state = setDefaultLocation(state, "t");
    expect(state.defaultId).toBe("t");
    expect(removeLocation(state, "t").defaultId).toBe(PRESET_LOCATION.id);
  });

  it("o preset não pode ser removido e id desconhecido não vira padrão", () => {
    expect(removeLocation(INITIAL_STATE, PRESET_LOCATION.id)).toBe(INITIAL_STATE);
    expect(setDefaultLocation(INITIAL_STATE, "x")).toBe(INITIAL_STATE);
  });

  it("ignora conteúdo corrompido ou inválido no armazenamento", () => {
    expect(loadLocations(memoryStorage({ [STORAGE_KEY]: "{não é json" }))).toEqual(INITIAL_STATE);
    const bad = JSON.stringify({
      locations: [{ id: "a", name: "A", lat: 200, lon: 0 }, { id: "b", name: "B", lat: -23, lon: -46 }],
      defaultId: "a",
    });
    const state = loadLocations(memoryStorage({ [STORAGE_KEY]: bad }));
    expect(state.locations.map((l) => l.id)).toEqual(["centro-sp", "b"]);
    expect(state.defaultId).toBe("centro-sp");
  });

  it("tolera navegador que recusa gravar", () => {
    const failing: StorageLike = {
      getItem: () => null,
      setItem: () => {
        throw new Error("QuotaExceededError");
      },
    };
    expect(saveLocations(failing, INITIAL_STATE)).toBe(false);
    expect(saveLocations(null, INITIAL_STATE)).toBe(false);
  });

  it("valida nome e coordenadas", () => {
    expect(validateLocation("", -23, -46)).toMatch(/nome/);
    expect(validateLocation("Casa", -95, -46)).toMatch(/Coordenadas inválidas/);
    expect(validateLocation("Casa", -23.5, -46.6)).toBeNull();
  });
});

describe("resolveSelectedLocation (FR-048)", () => {
  const params = (q: string) => new URLSearchParams(q);

  it("usa o local da URL quando válido", () => {
    expect(resolveSelectedLocation(params("lat=-23.6&lon=-46.7&nome=Casa"), [PRESET_LOCATION], "centro-sp")).toEqual({
      name: "Casa",
      lat: -23.6,
      lon: -46.7,
    });
  });

  it("cai no local padrão com URL ausente ou inválida", () => {
    expect(resolveSelectedLocation(params(""), [PRESET_LOCATION], "centro-sp").name).toBe("Centro de São Paulo");
    expect(resolveSelectedLocation(params("lat=abc&lon=1"), [PRESET_LOCATION], "centro-sp").lat).toBe(-23.5505);
  });
});
