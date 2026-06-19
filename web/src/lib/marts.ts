// Capa de datos del frontend: carga los marts Gold (JSON pequeños) generados por el pipeline.
// El frontend NO toca los millones de filas; solo estos agregados de pocos KB.

export type Source =
  | "perfil_contratante"
  | "agregaciones"
  | "encargos"
  | "contratos_menores";

export interface ResumenRow {
  source: Source;
  contratos: number;
  adjudicatarios: number;
  organos: number;
  importe: number | null;
  adjudicados: number;
  n_acuerdo_marco: number;
  importe_acuerdo_marco: number | null;
  n_anuladas: number;
  n_revisar: number;
  importe_revisar: number | null;
}
export interface SerieRow { year: number; source: Source; contratos: number; importe: number | null; }
export interface TerritorioRow { ccaa: string; year: number; source: Source; contratos: number; importe: number | null; }
export interface RankRow { nombre: string; id: string; source: Source; contratos: number; importe: number | null; n_acuerdo_marco?: number; }
export interface ContratoRow {
  id_origen: string | null;
  source: Source;
  estado: string | null;
  year: number | null;
  ccaa: string | null;
  objeto: string | null;
  organo_nombre: string | null;
  adjudicatario_nombre: string | null;
  importe: number | null;
  es_acuerdo_marco: boolean;
  revisar_importe: boolean;
  link_detalle: string | null;
}

export interface AnomaliaRow {
  id_origen: string | null;
  source: Source;
  year: number | null;
  ccaa: string | null;
  objeto: string | null;
  organo_nombre: string | null;
  adjudicatario_nombre: string | null;
  importe: number | null;
  cpv: string | null;
  peer: string;
  peers: number;
  es_acuerdo_marco: boolean;
  importe_mediano_peer: number | null;
  score: number | null;
  link_detalle: string | null;
}

export interface ConcentracionRow {
  organo_id: string | null;
  organo_nombre: string | null;
  source: Source;
  n_contratos: number;
  n_adjudicatarios: number;
  importe: number | null;
  hhi: number;
  top_proveedor: string | null;
  pct_dominante: number | null;
}
export interface FraccionamientoRow {
  organo_id: string | null;
  organo_nombre: string | null;
  adj_key: string | null;
  adjudicatario_nombre: string | null;
  n_cerca_umbral: number;
  importe_cerca: number | null;
  n_menores_total: number;
}

export interface Marts {
  resumen: ResumenRow[];
  serie: SerieRow[];
  territorio: TerritorioRow[];
  adjudicatarios: RankRow[];
  organos: RankRow[];
  contratos: ContratoRow[];
  anomalias: AnomaliaRow[];
  concentracion: ConcentracionRow[];
  fraccionamiento: FraccionamientoRow[];
}

const BASE = import.meta.env.BASE_URL + "data/";

async function getJSON<T>(name: string): Promise<T> {
  const res = await fetch(BASE + name + ".json");
  if (!res.ok) throw new Error(`No se pudo cargar el mart "${name}" (${res.status}). ¿Ejecutaste \`marts\`?`);
  return res.json() as Promise<T>;
}

export async function loadMarts(): Promise<Marts> {
  const [resumen, serie, territorio, adjudicatarios, organos, contratos, anomalias] =
    await Promise.all([
      getJSON<ResumenRow[]>("resumen"),
      getJSON<SerieRow[]>("serie_anual"),
      getJSON<TerritorioRow[]>("territorio"),
      getJSON<RankRow[]>("top_adjudicatarios"),
      getJSON<RankRow[]>("top_organos"),
      getJSON<ContratoRow[]>("top_contratos"),
      getJSON<AnomaliaRow[]>("anomalias"),
    ]);
  const [concentracion, fraccionamiento] = await Promise.all([
    getJSON<ConcentracionRow[]>("concentracion"),
    getJSON<FraccionamientoRow[]>("fraccionamiento"),
  ]);
  return {
    resumen, serie, territorio, adjudicatarios, organos, contratos, anomalias,
    concentracion, fraccionamiento,
  };
}

export const SOURCE_LABEL: Record<Source, string> = {
  perfil_contratante: "Perfil contratante",
  agregaciones: "Agregaciones",
  encargos: "Encargos",
  contratos_menores: "Contratos menores",
};

export const SOURCE_COVERAGE: Record<Source, string> = {
  perfil_contratante: "2012+",
  agregaciones: "2016+",
  encargos: "2022+",
  contratos_menores: "2018+",
};

// Abreviaturas de CCAA para la rejilla (cartograma).
export const CCAA_ABBR: Record<string, string> = {
  "Andalucía": "AND", "Aragón": "ARA", "Principado de Asturias": "AST",
  "Illes Balears": "BAL", "Canarias": "CNR", "Cantabria": "CTB",
  "Castilla y León": "CYL", "Castilla-La Mancha": "CLM", "Cataluña": "CAT",
  "Comunitat Valenciana": "CVA", "Extremadura": "EXT", "Galicia": "GAL",
  "Comunidad de Madrid": "MAD", "Región de Murcia": "MUR",
  "Comunidad Foral de Navarra": "NAV", "País Vasco": "PVA", "La Rioja": "RIO",
  "Ceuta": "CEU", "Melilla": "MEL",
};

const eurCompact = new Intl.NumberFormat("es-ES", {
  style: "currency", currency: "EUR", notation: "compact", maximumFractionDigits: 2,
});
const eurFull = new Intl.NumberFormat("es-ES", {
  style: "currency", currency: "EUR", maximumFractionDigits: 0,
});
const intFmt = new Intl.NumberFormat("es-ES");

export const eur = (n: number | null | undefined): string =>
  n == null ? "—" : Math.abs(n) >= 1e5 ? eurCompact.format(n) : eurFull.format(n);
export const num = (n: number | null | undefined): string =>
  n == null ? "—" : intFmt.format(n);

// Suma de importes/contratos por una clave, tolerando nulos.
export function sumBy<T>(rows: T[], key: (r: T) => string, val: (r: T) => number | null) {
  const m = new Map<string, number>();
  for (const r of rows) {
    const k = key(r);
    m.set(k, (m.get(k) ?? 0) + (val(r) ?? 0));
  }
  return m;
}
