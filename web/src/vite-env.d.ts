/// <reference types="vite/client" />

declare module "d3-composite-projections" {
  import type { GeoProjection } from "d3-geo";
  export function geoConicConformalSpain(): GeoProjection & { getCompositionBorders(): string };
}

