// Motor de consulta en el NAVEGADOR (DuckDB-WASM) sobre el índice Parquet de 5,08 M contratos.
// Local-first: los binarios WASM se sirven desde node_modules vía Vite (sin CDN). El Parquet se
// lee por HTTP con *range requests* (no se descarga entero; solo las columnas/row-groups que toca).

import * as duckdb from "@duckdb/duckdb-wasm";
import mvp_wasm from "@duckdb/duckdb-wasm/dist/duckdb-mvp.wasm?url";
import mvp_worker from "@duckdb/duckdb-wasm/dist/duckdb-browser-mvp.worker.js?url";
import eh_wasm from "@duckdb/duckdb-wasm/dist/duckdb-eh.wasm?url";
import eh_worker from "@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js?url";

const PARQUET = "contratos";
const PARQUET_URL = `${location.origin}${import.meta.env.BASE_URL}data/contratos.parquet`;

let connPromise: Promise<duckdb.AsyncDuckDBConnection> | null = null;

async function getConn(): Promise<duckdb.AsyncDuckDBConnection> {
  if (connPromise) return connPromise;
  connPromise = (async () => {
    const bundle = await duckdb.selectBundle({
      mvp: { mainModule: mvp_wasm, mainWorker: mvp_worker },
      eh: { mainModule: eh_wasm, mainWorker: eh_worker },
    });
    const worker = new Worker(bundle.mainWorker!);
    const db = new duckdb.AsyncDuckDB(new duckdb.ConsoleLogger(duckdb.LogLevel.WARNING), worker);
    await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
    await db.registerFileURL(PARQUET, PARQUET_URL, duckdb.DuckDBDataProtocol.HTTP, false);
    return db.connect();
  })();
  return connPromise;
}

/** Tabla origen para las consultas. */
export const SRC = `read_parquet('${PARQUET}')`;

/** Ejecuta SQL y devuelve filas como objetos JS. */
export async function query<T = Record<string, unknown>>(sql: string): Promise<T[]> {
  const conn = await getConn();
  const res = await conn.query(sql);
  return res.toArray().map((r) => r.toJSON() as T);
}

/** Escapa una cadena para interpolarla con seguridad en SQL (comillas simples). */
export function esc(s: string): string {
  return s.replace(/'/g, "''");
}

/** Inicializa el motor (para mostrar estado de carga antes de la primera consulta). */
export async function warmup(): Promise<void> {
  await query("SELECT 1");
}
