import { useEffect, useMemo, useState } from "react";
import {
  CCAA_ABBR,
  eur,
  loadMarts,
  num,
  SOURCE_COVERAGE,
  SOURCE_LABEL,
  sumBy,
  type Marts,
  type Source,
} from "./lib/marts";

type Filter = Source | "todas";
const SOURCES: Source[] = ["contratos_menores", "perfil_contratante", "agregaciones", "encargos"];
const PERIODS = ["2012–2026", "2018–2026", "2022–2026"];

export default function App() {
  const [marts, setMarts] = useState<Marts | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<Filter>("todas");
  const [period, setPeriod] = useState(PERIODS[0]);

  useEffect(() => {
    loadMarts().then(setMarts).catch((e) => setError(String(e.message ?? e)));
  }, []);

  const view = useMemo(() => {
    if (!marts) return null;
    const inSource = <T extends { source: Source }>(rows: T[]) =>
      source === "todas" ? rows : rows.filter((r) => r.source === source);

    const resumen = inSource(marts.resumen);
    const totalImporte = resumen.reduce((a, r) => a + (r.importe ?? 0), 0);
    const totalContratos = resumen.reduce((a, r) => a + r.contratos, 0);
    const totalAdj = resumen.reduce((a, r) => a + r.adjudicatarios, 0);

    const ccaaMap = sumBy(inSource(marts.territorio), (r) => r.ccaa, (r) => r.importe);
    const ccaa = [...ccaaMap.entries()]
      .map(([nombre, importe]) => ({ nombre, importe }))
      .sort((a, b) => b.importe - a.importe);
    const maxCcaa = ccaa[0]?.importe ?? 1;

    const serieMap = sumBy(inSource(marts.serie), (r) => String(r.year), (r) => r.importe);
    const serie = [...serieMap.entries()]
      .map(([y, importe]) => ({ year: +y, importe }))
      .sort((a, b) => a.year - b.year);
    const maxSerie = Math.max(...serie.map((s) => s.importe), 1);

    const adjMap = new Map<string, { nombre: string; importe: number; contratos: number }>();
    for (const r of inSource(marts.adjudicatarios)) {
      const cur = adjMap.get(r.id) ?? { nombre: r.nombre, importe: 0, contratos: 0 };
      cur.importe += r.importe ?? 0;
      cur.contratos += r.contratos;
      adjMap.set(r.id, cur);
    }
    const ranking = [...adjMap.values()].sort((a, b) => b.importe - a.importe).slice(0, 10);
    const maxRank = ranking[0]?.importe ?? 1;

    const amN = resumen.reduce((a, r) => a + (r.n_acuerdo_marco ?? 0), 0);
    const amImporte = resumen.reduce((a, r) => a + (r.importe_acuerdo_marco ?? 0), 0);
    const revN = resumen.reduce((a, r) => a + (r.n_revisar ?? 0), 0);
    const revImporte = resumen.reduce((a, r) => a + (r.importe_revisar ?? 0), 0);
    const contratos = (source === "todas"
      ? marts.contratos
      : marts.contratos.filter((c) => c.source === source)).slice(0, 12);
    const anomalias = (source === "todas"
      ? marts.anomalias
      : marts.anomalias.filter((a) => a.source === source)).slice(0, 12);
    const concentracion = (source === "todas"
      ? marts.concentracion
      : marts.concentracion.filter((c) => c.source === source)).slice(0, 12);
    const fraccionamiento = marts.fraccionamiento.slice(0, 12);
    const proveedores = marts.proveedores.slice(0, 12);

    return {
      totalImporte, totalContratos, totalAdj, ccaa, maxCcaa, serie, maxSerie, ranking, maxRank,
      amN, amImporte, revN, revImporte, contratos, anomalias, concentracion, fraccionamiento,
      proveedores,
    };
  }, [marts, source]);

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span>CONTRATACIÓN<span className="dot">·</span>ES</span>
          <span className="sub">contratación pública · 2012+</span>
        </div>
        <label className="search">
          <span>⌕</span>
          <input placeholder="Buscar órgano, proveedor, objeto, CPV…" aria-label="Buscar" />
          <span className="kbd">/</span>
        </label>
        <div className="period" role="group" aria-label="Periodo">
          {PERIODS.map((p) => (
            <button key={p} aria-pressed={period === p} onClick={() => setPeriod(p)}>{p}</button>
          ))}
        </div>
      </header>

      <aside className="rail">
        <div className="filter-group">
          <h2>Fuente</h2>
          <div className="chip-list">
            <button className="chip" aria-pressed={source === "todas"} onClick={() => setSource("todas")}>
              Todas
            </button>
            {SOURCES.map((s) => (
              <button key={s} className="chip" aria-pressed={source === s} onClick={() => setSource(s)}>
                {SOURCE_LABEL[s]}
              </button>
            ))}
          </div>
        </div>
        <div className="filter-group">
          <h2>Indicadores</h2>
          <div className="chip-list">
            {["Concentración proveedores", "Importes bajo umbral", "Alineación política"].map((f) => (
              <button key={f} className="chip" disabled title="Próximamente (Fase 2)">{f}</button>
            ))}
          </div>
        </div>
      </aside>

      <main className="canvas">
        {error && (
          <section className="card wide">
            <div className="card-head"><h3>Sin datos todavía</h3></div>
            <p style={{ color: "var(--ink-2)", lineHeight: 1.6 }}>
              {error}<br />
              Genera los marts con <code>python -m contratos_pipeline marts</code> y recarga.
            </p>
          </section>
        )}

        {!error && !view && (
          <section className="card wide"><div className="card-head"><h3>Cargando datos…</h3></div>
            <div className="spark">{Array.from({ length: 12 }).map((_, i) => (
              <div className="col" style={{ height: `${20 + (i % 5) * 15}%`, opacity: 0.4 }} key={i} />
            ))}</div>
          </section>
        )}

        {view && (
          <>
            <section className="card wide">
              <div className="card-head">
                <h3>Resumen</h3>
                <span className="meta">{period} · {source === "todas" ? "todas las fuentes" : SOURCE_LABEL[source as Source]} · <span className="badge">datos reales</span></span>
              </div>
              <div className="stat-row">
                <div className="stat"><div className="value">{eur(view.totalImporte)}</div><div className="label">Importe total (todo incluido)</div></div>
                <div className="stat"><div className="value">{num(view.totalContratos)}</div><div className="label">Contratos (deduplicados)</div></div>
                <div className="stat"><div className="value">{num(view.totalAdj)}</div><div className="label">Adjudicatarios</div></div>
              </div>
              {(view.amN > 0 || view.revN > 0) && (
                <p className="meta" style={{ marginTop: "var(--sp-3)" }}>
                  Composición: incluye {num(view.amN)} acuerdos marco ({eur(view.amImporte)} — son techos, no gasto)
                  {view.revN > 0 && <> · {num(view.revN)} a verificar ({eur(view.revImporte)})</>}. Nada se excluye del total.
                </p>
              )}
            </section>

            <section className="card">
              <div className="card-head"><h3>Gasto por CCAA</h3><span className="meta">importe canónico</span></div>
              <div className="map">
                {view.ccaa.slice(0, 18).map((c) => {
                  const norm = Math.sqrt(c.importe / view.maxCcaa);
                  const bucket = Math.min(6, Math.max(1, 1 + Math.floor(norm * 5.99)));
                  return (
                    <div className="cell" key={c.nombre} style={{ background: `var(--seq-${bucket})` }}
                      title={`${c.nombre}: ${eur(c.importe)}`}>
                      {CCAA_ABBR[c.nombre] ?? c.nombre.slice(0, 3).toUpperCase()}
                    </div>
                  );
                })}
              </div>
              {view.ccaa.length === 0 && <p className="meta">Sin territorio asignado en esta selección.</p>}
            </section>

            <section className="card">
              <div className="card-head"><h3>Top adjudicatarios</h3><span className="meta">por importe adjudicado</span></div>
              <div className="ranking">
                {view.ranking.map((r, i) => (
                  <div className="rank-row" key={r.nombre + i}>
                    <span className="idx">{i + 1}</span>
                    <span className="name" title={r.nombre}>{r.nombre}</span>
                    <span className="amount">{eur(r.importe)}</span>
                    <div className="bar" style={{ width: `${(r.importe / view.maxRank) * 100}%` }} />
                  </div>
                ))}
                {view.ranking.length === 0 && <p className="meta">Sin adjudicaciones en esta selección.</p>}
              </div>
            </section>

            <section className="card wide">
              <div className="card-head"><h3>Evolución del gasto</h3><span className="meta">por año</span></div>
              <div className="spark">
                {view.serie.map((s) => (
                  <div className="col" key={s.year}
                    style={{ height: `${Math.max(3, (s.importe / view.maxSerie) * 100)}%` }}
                    title={`${s.year}: ${eur(s.importe)}`} />
                ))}
              </div>
              <div className="meta" style={{ marginTop: "var(--sp-2)" }}>
                {view.serie.map((s) => s.year).join("  ·  ") || "—"}
              </div>
            </section>

            <section className="card wide">
              <div className="card-head">
                <h3>Contratos más grandes</h3>
                <span className="meta">objetividad · nada se oculta</span>
              </div>
              <div className="biglist">
                {view.contratos.map((c, i) => (
                  <div className="big-row" key={(c.id_origen ?? "") + i}>
                    <span className="amount">{eur(c.importe)}</span>
                    <span className="tags">
                      {c.es_acuerdo_marco && <span className="tag tag-am">acuerdo marco</span>}
                      {c.revisar_importe && <span className="tag tag-rev">a verificar</span>}
                    </span>
                    <span className="name" title={c.objeto ?? ""}>
                      {c.adjudicatario_nombre || c.organo_nombre || c.objeto || "—"}
                    </span>
                    {c.link_detalle && (
                      <a className="ext" href={c.link_detalle} target="_blank" rel="noreferrer" title="Ver en PLACSP">↗</a>
                    )}
                  </div>
                ))}
              </div>
            </section>

            <section className="card wide">
              <div className="card-head">
                <h3>Anomalías de importe</h3>
                <span className="meta">vs contratos similares (CPV + tipo) · score robusto · descriptivo, no concluyente</span>
              </div>
              <div className="biglist">
                {view.anomalias.map((a, i) => (
                  <div className="big-row" key={(a.id_origen ?? "") + i}>
                    <span className="amount">{eur(a.importe)}</span>
                    <span className="tags">
                      <span className="tag tag-rev">×{a.score} σ</span>
                      {a.es_acuerdo_marco && <span className="tag tag-am">acuerdo marco</span>}
                    </span>
                    <span className="name" title={a.objeto ?? ""}>
                      {a.adjudicatario_nombre || a.organo_nombre || a.objeto || "—"}
                      <span className="muted"> · mediana similares {eur(a.importe_mediano_peer)} ({num(a.peers)} pares)</span>
                    </span>
                    {a.link_detalle && (
                      <a className="ext" href={a.link_detalle} target="_blank" rel="noreferrer" title="Ver en PLACSP">↗</a>
                    )}
                  </div>
                ))}
                {view.anomalias.length === 0 && <p className="meta">Aún sin marts de anomalías (ejecuta `marts`).</p>}
              </div>
            </section>

            <section className="card">
              <div className="card-head">
                <h3>Concentración por órgano</h3>
                <span className="meta">HHI sobre nº de adjudicaciones</span>
              </div>
              <div className="biglist">
                {view.concentracion.map((c, i) => (
                  <div className="big-row" key={(c.organo_id ?? "") + i}>
                    <span className="amount">HHI {c.hhi.toFixed(2)}</span>
                    <span className="tags"><span className="tag tag-rev">{c.pct_dominante}%</span></span>
                    <span className="name" title={c.organo_nombre ?? ""}>
                      {c.organo_nombre}
                      <span className="muted"> → {c.top_proveedor} · {c.n_contratos} contr, {c.n_adjudicatarios} prov</span>
                    </span>
                  </div>
                ))}
              </div>
            </section>

            <section className="card">
              <div className="card-head">
                <h3>Fraccionamiento (menores)</h3>
                <span className="meta">menores pegados al umbral legal</span>
              </div>
              <div className="biglist">
                {view.fraccionamiento.map((f, i) => (
                  <div className="big-row" key={(f.organo_id ?? "") + (f.adj_key ?? "") + i}>
                    <span className="amount">{f.n_cerca_umbral}×</span>
                    <span className="tags"><span className="tag tag-rev">cerca umbral</span></span>
                    <span className="name" title={f.organo_nombre ?? ""}>
                      {f.organo_nombre} → {f.adjudicatario_nombre}
                      <span className="muted"> · {eur(f.importe_cerca)} de {num(f.n_menores_total)} menores</span>
                    </span>
                  </div>
                ))}
              </div>
            </section>

            <section className="card wide">
              <div className="card-head">
                <h3>Proveedores recurrentes</h3>
                <span className="meta">importe · nº de órganos · dependencia de uno solo</span>
              </div>
              <div className="biglist">
                {view.proveedores.map((p, i) => (
                  <div className="big-row" key={(p.id ?? "") + i}>
                    <span className="amount">{eur(p.importe)}</span>
                    <span className="tags">
                      <span className="tag tag-am">{num(p.n_organos)} órganos · {p.pct_top_organo}% de 1</span>
                    </span>
                    <span className="name" title={p.top_organo ?? ""}>
                      {p.nombre}
                      <span className="muted"> · {num(p.n_contratos)} contratos</span>
                    </span>
                  </div>
                ))}
              </div>
            </section>
          </>
        )}
      </main>

      <aside className="context">
        <h2>Contexto del dato</h2>
        <div className="kv"><span className="k">Fuente</span><span className="v">PLACSP · datos.gob.es</span></div>
        <div className="kv"><span className="k">Periodo cargado</span><span className="v">2024–2026 (histórico en progreso)</span></div>
        <div className="kv"><span className="k">Cobertura por fuente</span>
          <span className="v">{SOURCES.map((s) => `${SOURCE_LABEL[s]} ${SOURCE_COVERAGE[s]}`).join(" · ")}</span>
        </div>
        <div className="kv"><span className="k">Normalización</span><span className="v">Registro canónico por expediente (estado final)</span></div>
        <div className="disclaimer">
          Importes <strong>deduplicados</strong> al estado final de cada expediente. Los indicadores
          son <strong>señales para investigar, no acusaciones</strong>. Correlación no implica causalidad.
        </div>
      </aside>

      <footer className="footer">
        <span>Datos públicos reutilizables · PLACSP</span>
        <span>·</span>
        <span>Fase 1 — datos reales (marts Gold)</span>
      </footer>
    </div>
  );
}
