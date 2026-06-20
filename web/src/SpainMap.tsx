import { useMemo, useState } from "react";
import { geoPath } from "d3-geo";
import { geoConicConformalSpain } from "d3-composite-projections";
import { feature } from "topojson-client";
import atlas from "es-atlas/es/autonomous_regions.json";

// es-atlas usa nombres como "Cataluña/Catalunya" o "Ciudad Autónoma de Ceuta";
// los normalizamos a los nombres de CCAA que produce el pipeline (vía NUTS).
const toCcaa = (name: string): string =>
  name.split("/")[0].trim().replace("Ciudad Autónoma de ", "");

const W = 680;
const H = 440;

export function SpainMap({
  data,
  format,
  onSelect,
}: {
  data: Map<string, number>;
  format: (n: number) => string;
  onSelect?: (ccaa: string) => void;
}) {
  const [hover, setHover] = useState<string | null>(null);

  const { feats, path, borders } = useMemo(() => {
    const fc = feature(atlas as never, (atlas as never as { objects: Record<string, never> }).objects.autonomous_regions) as unknown as {
      features: { properties: { name: string } }[];
    };
    const proj = geoConicConformalSpain().fitSize([W, H], fc as never);
    const path = geoPath(proj);
    const borders = proj.getCompositionBorders() as string;
    return { feats: fc.features, path, borders };
  }, []);

  // Escala de color LOGARÍTMICA: los importes están muy sesgados (un solo outlier —Madrid por el
  // efecto sede— multiplica por ~8 al siguiente), así que una escala lineal dejaría a casi todas las
  // CCAA en el tono más claro e indistinguibles. El log mantiene el color monótono con el importe
  // (más oscuro = más gasto) pero reparte los tonos por orden de magnitud. Los valores exactos
  // siguen visibles en el ranking y en el tooltip; nada se oculta ni se distorsiona el orden.
  const { lmin, lspan } = useMemo(() => {
    const vals = Array.from(data.values()).filter((v) => v > 0);
    const max = Math.max(...vals, 1);
    const min = Math.min(...vals, max);
    const lmin = Math.log(min);
    const lspan = Math.log(max) - lmin || 1;
    return { lmin, lspan };
  }, [data]);
  const bucket = (v: number) =>
    v > 0 ? Math.min(6, Math.max(1, 1 + Math.floor(((Math.log(v) - lmin) / lspan) * 5.999))) : 1;

  const caption = hover
    ? `${hover} · ${data.has(hover) ? format(data.get(hover)!) : "sin dato"} · clic para investigar`
    : "Pasa el ratón por una comunidad · clic para investigarla";

  return (
    <div className="spainmap">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Mapa de España por comunidad autónoma">
        {feats.map((f, i) => {
          const ccaa = toCcaa(f.properties?.name ?? "");
          const v = data.get(ccaa);
          return (
            <path
              key={i}
              d={path(f as never) ?? ""}
              className={`ccaa${hover === ccaa ? " hov" : ""}`}
              style={{ fill: v != null ? `var(--seq-${bucket(v)})` : "var(--surface-2)" }}
              data-tip={`${ccaa}: ${v != null ? format(v) : "sin dato"}`}
              onMouseEnter={() => setHover(ccaa)}
              onMouseLeave={() => setHover(null)}
              onClick={() => onSelect?.(ccaa)}
            />
          );
        })}
        <path d={borders} className="mapborder" />
      </svg>
      <div className="mapcap">{caption}</div>
      <div className="maplegend" aria-hidden="true">
        <span>menos</span>
        {[1, 2, 3, 4, 5, 6].map((b) => (
          <i key={b} style={{ background: `var(--seq-${b})` }} />
        ))}
        <span>más</span>
        <span className="leg-note">escala logarítmica</span>
      </div>
    </div>
  );
}
