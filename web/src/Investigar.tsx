import { useEffect, useState } from "react";
import { eur, num, SOURCE_LABEL, type Source } from "./lib/marts";
import { esc, query, SRC, warmup } from "./lib/db";

interface Contrato {
  id_origen: string | null;
  source: Source;
  fichero: string | null;
  estado: string | null;
  year: number | null;
  organo_nombre: string | null;
  organo_nif: string | null;
  organo_nivel: string | null;
  ccaa: string | null;
  cpv: string | null;
  tipo_contrato: string | null;
  adjudicatario_nombre: string | null;
  adjudicatario_nif: string | null;
  fecha_adjudicacion: string | null;
  importe: number | null;
  importe_adjudicado: number | null;
  importe_total_con_iva: number | null;
  importe_sin_iva: number | null;
  es_acuerdo_marco: boolean;
  revisar_importe: boolean;
  link_detalle: string | null;
}

const COLS =
  "id_origen, source, fichero, estado, year, organo_nombre, organo_nif, organo_nivel, ccaa, " +
  "cpv, tipo_contrato, adjudicatario_nombre, adjudicatario_nif, fecha_adjudicacion, importe, " +
  "importe_adjudicado, importe_total_con_iva, importe_sin_iva, es_acuerdo_marco, " +
  "revisar_importe, link_detalle";

const N = (v: unknown): number => (v == null ? 0 : Number(v));

const emptyFilters = {
  adjudicatario: "", organo: "", nif: "", ccaa: "", cpv: "", year: "",
  source: "", estado: "", minImporte: "", maxImporte: "", revisar: false, acuerdoMarco: false,
};
type Filters = typeof emptyFilters;

function buildWhere(f: Filters): string {
  const c: string[] = [];
  if (f.adjudicatario) c.push(`adjudicatario_nombre ILIKE '%${esc(f.adjudicatario)}%'`);
  if (f.organo) c.push(`organo_nombre ILIKE '%${esc(f.organo)}%'`);
  if (f.nif) c.push(`(adjudicatario_nif = '${esc(f.nif)}' OR organo_nif = '${esc(f.nif)}')`);
  if (f.ccaa) c.push(`ccaa ILIKE '%${esc(f.ccaa)}%'`);
  if (f.cpv) c.push(`cpv LIKE '${esc(f.cpv)}%'`);
  if (f.source) c.push(`source = '${esc(f.source)}'`);
  if (f.estado) c.push(`estado = '${esc(f.estado.toUpperCase())}'`);
  if (f.year && /^\d{4}$/.test(f.year)) c.push(`year = ${parseInt(f.year, 10)}`);
  if (f.minImporte && !isNaN(Number(f.minImporte))) c.push(`importe >= ${Number(f.minImporte)}`);
  if (f.maxImporte && !isNaN(Number(f.maxImporte))) c.push(`importe <= ${Number(f.maxImporte)}`);
  if (f.revisar) c.push("revisar_importe");
  if (f.acuerdoMarco) c.push("es_acuerdo_marco");
  return c.length ? "WHERE " + c.join(" AND ") : "";
}

export default function Investigar() {
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const [rows, setRows] = useState<Contrato[] | null>(null);
  const [stats, setStats] = useState<{ n: number; imp: number; adj: number; org: number } | null>(null);
  const [sel, setSel] = useState<Contrato | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    warmup().then(() => setReady(true)).catch((e) => setError(String(e.message ?? e)));
  }, []);

  const set = (k: keyof Filters, v: string | boolean) => setFilters((f) => ({ ...f, [k]: v }));

  async function buscar() {
    setBusy(true);
    setError(null);
    setSel(null);
    try {
      const where = buildWhere(filters);
      const data = await query<Contrato>(
        `SELECT ${COLS} FROM ${SRC} ${where} ORDER BY importe DESC NULLS LAST LIMIT 200`,
      );
      const [s] = await query<Record<string, unknown>>(
        `SELECT count(*) n, sum(importe) imp, count(DISTINCT adjudicatario_nif) adj,
                count(DISTINCT organo_nif) org FROM ${SRC} ${where}`,
      );
      setRows(data);
      setStats({ n: N(s.n), imp: N(s.imp), adj: N(s.adj), org: N(s.org) });
    } catch (e) {
      setError(String((e as Error).message ?? e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <section className="card wide">
        <div className="card-head">
          <h3>Buscar contratos</h3>
          <span className="meta">
            {ready ? "5,08 M contratos · motor en el navegador (DuckDB-WASM)" : "inicializando motor…"}
          </span>
        </div>
        <div className="investiga-form">
          <label>Adjudicatario<input value={filters.adjudicatario} onChange={(e) => set("adjudicatario", e.target.value)} placeholder="p. ej. DRAGADOS" /></label>
          <label>Órgano<input value={filters.organo} onChange={(e) => set("organo", e.target.value)} placeholder="p. ej. Ayuntamiento de…" /></label>
          <label>NIF (órgano o adj.)<input value={filters.nif} onChange={(e) => set("nif", e.target.value)} /></label>
          <label>CCAA<input value={filters.ccaa} onChange={(e) => set("ccaa", e.target.value)} placeholder="Madrid" /></label>
          <label>CPV (prefijo)<input value={filters.cpv} onChange={(e) => set("cpv", e.target.value)} /></label>
          <label>Año<input value={filters.year} onChange={(e) => set("year", e.target.value)} placeholder="2023" /></label>
          <label>Fuente
            <select value={filters.source} onChange={(e) => set("source", e.target.value)}>
              <option value="">todas</option>
              {(["contratos_menores", "perfil_contratante", "agregaciones", "encargos"] as Source[]).map((s) => (
                <option key={s} value={s}>{SOURCE_LABEL[s]}</option>
              ))}
            </select>
          </label>
          <label>Estado<input value={filters.estado} onChange={(e) => set("estado", e.target.value)} placeholder="RES, ADJ…" /></label>
          <label>Importe ≥<input value={filters.minImporte} onChange={(e) => set("minImporte", e.target.value)} placeholder="€" /></label>
          <label>Importe ≤<input value={filters.maxImporte} onChange={(e) => set("maxImporte", e.target.value)} placeholder="€" /></label>
          <label className="chk"><input type="checkbox" checked={filters.revisar} onChange={(e) => set("revisar", e.target.checked)} /> a verificar</label>
          <label className="chk"><input type="checkbox" checked={filters.acuerdoMarco} onChange={(e) => set("acuerdoMarco", e.target.checked)} /> acuerdo marco</label>
        </div>
        <div className="investiga-actions">
          <button className="btn" onClick={buscar} disabled={!ready || busy}>{busy ? "Buscando…" : "Buscar"}</button>
          <button className="btn ghost" onClick={() => { setFilters(emptyFilters); setRows(null); setStats(null); setSel(null); }}>Limpiar</button>
          {stats && (
            <span className="meta">
              {num(stats.n)} contratos · {eur(stats.imp)} · {num(stats.adj)} adjudicatarios · {num(stats.org)} órganos
              {stats.n > 200 && " · (mostrando 200)"}
            </span>
          )}
        </div>
        {error && <p className="meta" style={{ color: "var(--warn)" }}>Error: {error}</p>}
      </section>

      {sel && (
        <section className="card wide">
          <div className="card-head">
            <h3>Ficha del contrato</h3>
            <button className="btn ghost" onClick={() => setSel(null)}>cerrar ✕</button>
          </div>
          <div className="ficha">
            {([
              ["Expediente", sel.id_origen], ["Estado", sel.estado], ["Fuente", sel.source],
              ["Órgano", sel.organo_nombre], ["NIF órgano", sel.organo_nif], ["Nivel", sel.organo_nivel],
              ["CCAA", sel.ccaa], ["CPV", sel.cpv],
              ["Adjudicatario", sel.adjudicatario_nombre], ["NIF adj.", sel.adjudicatario_nif],
              ["Fecha adj.", sel.fecha_adjudicacion], ["Año", sel.year],
              ["Importe", eur(N(sel.importe))], ["Importe adjudicado", sel.importe_adjudicado != null ? eur(N(sel.importe_adjudicado)) : "—"],
              ["Presupuesto (c/IVA)", sel.importe_total_con_iva != null ? eur(N(sel.importe_total_con_iva)) : "—"],
              ["Presupuesto (s/IVA)", sel.importe_sin_iva != null ? eur(N(sel.importe_sin_iva)) : "—"],
            ] as [string, unknown][]).map(([k, v]) => (
              <div className="kv" key={k}><span className="k">{k}</span><span className="v">{String(v ?? "—")}</span></div>
            ))}
          </div>
          <div className="tags" style={{ margin: "var(--sp-2) 0" }}>
            {sel.es_acuerdo_marco && <span className="tag tag-am">acuerdo marco</span>}
            {sel.revisar_importe && <span className="tag tag-rev">a verificar</span>}
          </div>
          <p className="meta"><strong>Fichero de origen</strong> (ábrelo y busca «{sel.id_origen}» para verificar):</p>
          <p className="filepath">data/{sel.fichero}</p>
          {sel.link_detalle && <p className="meta"><a className="ext" href={sel.link_detalle} target="_blank" rel="noreferrer">Ver ficha oficial en PLACSP ↗</a></p>}
        </section>
      )}

      <section className="card wide">
        <div className="card-head"><h3>Resultados</h3><span className="meta">clica una fila para ver su ficha y fichero</span></div>
        {rows == null && <p className="meta">Define filtros y pulsa «Buscar».</p>}
        {rows != null && rows.length === 0 && <p className="meta">Sin resultados para esos filtros.</p>}
        {rows != null && rows.length > 0 && (
          <div className="results-wrap">
            <table className="results">
              <thead><tr><th>importe</th><th>expediente</th><th>adjudicatario</th><th>órgano</th><th>CCAA</th><th>fuente/año</th></tr></thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={(r.id_origen ?? "") + i} onClick={() => setSel(r)} className={sel === r ? "on" : ""}>
                    <td className="amt">{eur(N(r.importe))}{r.revisar_importe ? " ⚑" : ""}</td>
                    <td>{r.id_origen}</td>
                    <td className="tx">{r.adjudicatario_nombre || "—"}</td>
                    <td className="tx">{r.organo_nombre || "—"}</td>
                    <td>{r.ccaa || "—"}</td>
                    <td className="dim">{(r.source || "").slice(0, 6)}/{r.year}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
