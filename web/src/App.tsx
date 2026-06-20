import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import {
  eur,
  loadMarts,
  num,
  SOURCE_COVERAGE,
  SOURCE_LABEL,
  sumBy,
  type Marts,
  type Source,
} from "./lib/marts";
import { SpainMap } from "./SpainMap";

const Investigar = lazy(() => import("./Investigar"));

type Filter = Source | "todas";
type SectionId = "resumen" | "investigar" | "territorio" | "proveedores" | "patrones" | "metodologia";

const SOURCES: Source[] = ["contratos_menores", "perfil_contratante", "agregaciones", "encargos"];
const PERIODS = ["2012–2026", "2018–2026", "2022–2026"];
const SECTIONS: { id: SectionId; label: string; sub: string }[] = [
  { id: "resumen", label: "Resumen", sub: "el panorama y su composición" },
  { id: "investigar", label: "Investigar", sub: "buscar y filtrar contratos uno a uno" },
  { id: "territorio", label: "Territorio", sub: "gasto por comunidad autónoma" },
  { id: "proveedores", label: "Proveedores", sub: "recurrentes, dependencia y concentración" },
  { id: "patrones", label: "Patrones llamativos", sub: "contratos grandes, anomalías, fraccionamiento" },
  { id: "metodologia", label: "Cómo leer esto", sub: "metodología y cautelas" },
];

export default function App() {
  const [marts, setMarts] = useState<Marts | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<Filter>("todas");
  const [period, setPeriod] = useState(PERIODS[0]);
  const [section, setSection] = useState<SectionId>("resumen");
  const [territorioMode, setTerritorioMode] = useState<"total" | "percapita">("total");
  const [q, setQ] = useState("");
  const [seed, setSeed] = useState<{ text: string; nonce: number } | null>(null);

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
    const amN = resumen.reduce((a, r) => a + (r.n_acuerdo_marco ?? 0), 0);
    const amImporte = resumen.reduce((a, r) => a + (r.importe_acuerdo_marco ?? 0), 0);
    const revN = resumen.reduce((a, r) => a + (r.n_revisar ?? 0), 0);
    const revImporte = resumen.reduce((a, r) => a + (r.importe_revisar ?? 0), 0);

    const ccaaMap = sumBy(inSource(marts.territorio), (r) => r.ccaa, (r) => r.importe);
    const ccaa = [...ccaaMap.entries()]
      .map(([nombre, importe]) => ({ nombre, importe }))
      .sort((a, b) => b.importe - a.importe);
    const maxCcaa = ccaa[0]?.importe ?? 1;

    // Per cápita (€/persona acumulado) — todas las fuentes, independiente del filtro de fuente.
    const ccaaPCMap = sumBy(marts.territorioPercapita, (r) => r.ccaa, (r) => r.per_capita);
    const ccaaPC = [...ccaaPCMap.entries()]
      .map(([nombre, importe]) => ({ nombre, importe }))
      .sort((a, b) => b.importe - a.importe);
    const maxCcaaPC = ccaaPC[0]?.importe ?? 1;

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

    const filt = <T extends { source: Source }>(rows: T[], n: number) =>
      (source === "todas" ? rows : rows.filter((r) => r.source === source)).slice(0, n);

    return {
      totalImporte, totalContratos, totalAdj, amN, amImporte, revN, revImporte,
      ccaa, maxCcaa, ccaaPC, maxCcaaPC, serie, maxSerie, ranking, maxRank,
      contratos: filt(marts.contratos, 12),
      anomalias: filt(marts.anomalias, 12),
      concentracion: filt(marts.concentracion, 12),
      proveedores: marts.proveedores.slice(0, 12),
      fraccionamiento: marts.fraccionamiento.slice(0, 12),
    };
  }, [marts, source]);

  const active = SECTIONS.find((s) => s.id === section)!;
  const sourceLabel = source === "todas" ? "todas las fuentes" : SOURCE_LABEL[source as Source];

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span>CONTRATACIÓN<span className="dot">·</span>ES</span>
          <span className="sub">registro de contratación pública · 2012+</span>
        </div>
        <form
          className="search"
          onSubmit={(e) => {
            e.preventDefault();
            const t = q.trim();
            if (!t) return;
            setSection("investigar");
            setSeed({ text: t, nonce: Date.now() });
          }}
        >
          <span aria-hidden>⌕</span>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar proveedor o NIF → Investigar"
            aria-label="Buscar"
          />
          <button type="submit" className="kbd" aria-label="Buscar">↵</button>
        </form>
        <div className="period" role="group" aria-label="Periodo">
          {PERIODS.map((p) => (
            <button key={p} aria-pressed={period === p} onClick={() => setPeriod(p)}>{p}</button>
          ))}
        </div>
      </header>

      <aside className="rail">
        <h2>Índice del expediente</h2>
        <nav className="index">
          {SECTIONS.map((s, i) => (
            <button
              key={s.id}
              className="folio"
              aria-current={section === s.id ? "page" : undefined}
              onClick={() => setSection(s.id)}
            >
              <span className="num">{String(i + 1).padStart(2, "0")}</span>
              <span className="lbl">
                <span className="t">{s.label}</span>
                <span className="s">{s.sub}</span>
              </span>
            </button>
          ))}
        </nav>

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
      </aside>

      <main className="canvas">
        <div className="section-head">
          <h1>{active.label}</h1>
          <span className="meta">{active.sub} · {period} · {sourceLabel}</span>
        </div>

        {section === "investigar" && (
          <Suspense fallback={
            <section className="card wide">
              <div className="card-head"><h3>Cargando motor de consulta…</h3></div>
              <p className="meta">Inicializando DuckDB-WASM en el navegador (la primera vez tarda unos segundos).</p>
            </section>
          }>
            <Investigar seed={seed} />
          </Suspense>
        )}

        {section !== "investigar" && error && (
          <section className="card wide">
            <div className="card-head"><h3>Sin datos todavía</h3></div>
            <p className="muted" style={{ lineHeight: 1.6 }}>
              {error}<br />Genera los marts con <code>python -m contratos_pipeline marts</code> y recarga.
            </p>
          </section>
        )}

        {section !== "investigar" && !error && !view && (
          <section className="card wide">
            <div className="card-head"><h3>Cargando expediente…</h3></div>
            <div className="spark">{Array.from({ length: 12 }).map((_, i) => (
              <div className="col" style={{ height: `${20 + (i % 5) * 15}%`, opacity: 0.4 }} key={i} />
            ))}</div>
          </section>
        )}

        {view && section === "resumen" && (
          <>
            <section className="card wide">
              <div className="card-head">
                <h3>Cifras del periodo</h3>
                <span className="meta"><span className="badge">datos reales</span></span>
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
          </>
        )}

        {view && section === "territorio" && (() => {
          const pc = territorioMode === "percapita";
          const arr = [...(pc ? view.ccaaPC : view.ccaa)].sort((a, b) => (b.importe || 0) - (a.importe || 0));
          const mapData = new Map(arr.map((c) => [c.nombre, c.importe] as const));
          const fmt = (n: number) => eur(n) + (pc ? " /persona" : "");
          return (
            <section className="card wide">
              <div className="card-head">
                <h3>Gasto por comunidad autónoma</h3>
                <div className="period" role="group" aria-label="Modo territorio">
                  <button aria-pressed={!pc} onClick={() => setTerritorioMode("total")}>Total</button>
                  <button aria-pressed={pc} onClick={() => setTerritorioMode("percapita")}>Per cápita</button>
                </div>
              </div>
              <div className="territorio-grid">
                <SpainMap data={mapData} format={fmt} />
                <ol className="ccaa-rank">
                  {arr.slice(0, 12).map((c, i) => (
                    <li key={c.nombre}>
                      <span className="r-idx">{i + 1}</span>
                      <span className="r-name" title={c.nombre}>{c.nombre}</span>
                      <span className="r-val">{fmt(c.importe)}</span>
                    </li>
                  ))}
                </ol>
              </div>
              {arr.length === 0 && <p className="meta">Sin territorio asignado.</p>}
              <p className="meta" style={{ marginTop: "var(--sp-3)" }}>
                {pc
                  ? "€/persona acumulado 2012–2026 (población INE). Color en escala logarítmica; los valores exactos están en el ranking. Excluye errores marcados; incluye acuerdos marco. La contratación estatal aún pesa hacia Madrid (efecto sede)."
                  : "Importe total acumulado 2012–2026. Color en escala logarítmica; los valores exactos están en el ranking. La contratación estatal se registra en la sede del organismo (efecto Madrid)."}
              </p>
            </section>
          );
        })()}

        {view && section === "proveedores" && (
          <>
            <section className="card">
              <div className="card-head"><h3>Top adjudicatarios</h3><span className="meta">por importe</span></div>
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

            <section className="card">
              <div className="card-head"><h3>Concentración por órgano</h3><span className="meta">HHI sobre nº de adjudicaciones</span></div>
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

            <section className="card wide">
              <div className="card-head"><h3>Proveedores recurrentes</h3><span className="meta">importe · nº de órganos · dependencia de uno solo</span></div>
              <div className="biglist">
                {view.proveedores.map((p, i) => (
                  <div className="big-row" key={(p.id ?? "") + i}>
                    <span className="amount">{eur(p.importe)}</span>
                    <span className="tags"><span className="tag tag-am">{num(p.n_organos)} órganos · {p.pct_top_organo}% de 1</span></span>
                    <span className="name" title={p.top_organo ?? ""}>
                      {p.nombre}<span className="muted"> · {num(p.n_contratos)} contratos</span>
                    </span>
                  </div>
                ))}
              </div>
            </section>
          </>
        )}

        {view && section === "patrones" && (
          <>
            <section className="card wide">
              <div className="card-head"><h3>Contratos más grandes</h3><span className="meta">objetividad · nada se oculta</span></div>
              <div className="biglist">
                {view.contratos.map((c, i) => (
                  <div className="big-row" key={(c.id_origen ?? "") + i}>
                    <span className="amount">{eur(c.importe)}</span>
                    <span className="tags">
                      {c.es_acuerdo_marco && <span className="tag tag-am">acuerdo marco</span>}
                      {c.revisar_importe && <span className="tag tag-rev">a verificar</span>}
                    </span>
                    <span className="name" title={c.objeto ?? ""}>{c.adjudicatario_nombre || c.organo_nombre || c.objeto || "—"}</span>
                    {c.link_detalle && <a className="ext" href={c.link_detalle} target="_blank" rel="noreferrer" title="Ver en PLACSP">↗</a>}
                  </div>
                ))}
              </div>
            </section>

            <section className="card wide">
              <div className="card-head"><h3>Anomalías de importe</h3><span className="meta">vs contratos similares (CPV + tipo) · descriptivo, no concluyente</span></div>
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
                    {a.link_detalle && <a className="ext" href={a.link_detalle} target="_blank" rel="noreferrer" title="Ver en PLACSP">↗</a>}
                  </div>
                ))}
              </div>
            </section>

            <section className="card wide">
              <div className="card-head"><h3>Fraccionamiento (menores)</h3><span className="meta">menores pegados al umbral legal 15k/40k</span></div>
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
          </>
        )}

        {view && section === "metodologia" && (
          <>
            <section className="card wide">
              <div className="card-head"><h3>Cómo leer estos datos</h3><span className="meta">presentación responsable</span></div>
              <div className="prose">
                <p><strong>Señales, no acusaciones.</strong> Concentración, anomalías o fraccionamiento son patrones para <em>investigar</em>, no pruebas. Correlación no implica causalidad.</p>
                <p><strong>Expediente canónico.</strong> Los feeds republican cada contrato en cada cambio de estado; nos quedamos con una fila por (fuente, órgano, expediente), la más reciente. Sin esto, los importes se multiplican (perfil ×3,6).</p>
                <p><strong>Importes: nada se oculta.</strong> El total incluye todo. Los <span className="tag tag-am">acuerdo marco</span> son techos (no gasto ejecutado). Los importes físicamente imposibles (p. ej. €200 B a una persona) se marcan <span className="tag tag-rev">a verificar</span>, jamás se borran.</p>
                <p><strong>Anomalías sin prejuicios.</strong> No fijamos qué es "normal": cada contrato se compara con sus <em>similares</em> (CPV + tipo) y la propia distribución decide qué es atípico.</p>
                <p><strong>Per cápita.</strong> Población INE para comparar de forma justa. Aun así, la contratación estatal se registra en la sede del organismo (efecto Madrid), que la normalización no elimina.</p>
              </div>
            </section>

            <section className="card wide">
              <div className="card-head"><h3>Cobertura por fuente</h3><span className="meta">desde qué año hay datos</span></div>
              <div className="biglist">
                {SOURCES.map((s) => (
                  <div className="big-row" key={s}>
                    <span className="amount">{SOURCE_COVERAGE[s]}</span>
                    <span className="tags" />
                    <span className="name">{SOURCE_LABEL[s]}</span>
                  </div>
                ))}
              </div>
            </section>
          </>
        )}
      </main>

      <aside className="context">
        <h2>Sello del expediente</h2>
        <div className="kv"><span className="k">Fuente</span><span className="v">PLACSP · datos.gob.es</span></div>
        <div className="kv"><span className="k">Periodo cargado</span><span className="v">2012–2026</span></div>
        <div className="kv"><span className="k">Cobertura por fuente</span>
          <span className="v">{SOURCES.map((s) => `${SOURCE_LABEL[s]} ${SOURCE_COVERAGE[s]}`).join(" · ")}</span>
        </div>
        <div className="kv"><span className="k">Normalización</span><span className="v">Registro canónico por expediente (estado final)</span></div>
        <div className="disclaimer">
          Indicadores como concentración, anomalías o fraccionamiento son <strong>señales para
          investigar, no acusaciones</strong>. Correlación no implica causalidad. Nada se oculta;
          los posibles errores se <strong>marcan</strong>, no se borran.
        </div>
      </aside>

      <footer className="footer">
        <span>Datos públicos reutilizables · PLACSP</span>
        <span>·</span>
        <span>Fase 2 — análisis sobre 2012–2026</span>
      </footer>
    </div>
  );
}
