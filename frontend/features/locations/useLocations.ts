"use client";

import { useCallback, useEffect, useState } from "react";
import {
  INITIAL_STATE,
  addLocation,
  loadLocations,
  removeLocation,
  saveLocations,
  setDefaultLocation,
  type LocationsState,
  type SavedLocation,
  type StorageLike,
} from "./store";

function browserStorage(): StorageLike | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function useLocations() {
  const [state, setState] = useState<LocationsState>(INITIAL_STATE);
  const [persisted, setPersisted] = useState(true);

  // Lê depois de montar, para o HTML do servidor e o do navegador serem iguais.
  useEffect(() => {
    setState(loadLocations(browserStorage()));
  }, []);

  const update = useCallback((next: (s: LocationsState) => LocationsState) => {
    setState((current) => {
      const value = next(current);
      setPersisted(saveLocations(browserStorage(), value));
      return value;
    });
  }, []);

  return {
    ...state,
    persisted,
    add: (location: Omit<SavedLocation, "id">) => update((s) => addLocation(s, location)),
    remove: (id: string) => update((s) => removeLocation(s, id)),
    setDefault: (id: string) => update((s) => setDefaultLocation(s, id)),
  };
}
