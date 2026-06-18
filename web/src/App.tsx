import { useState } from "react";

// NOTA: datos de MUESTRA para validar el sistema visual de la Fase 0.
// En Fase 1 se sustituyen por los marts Gold reales (web/public/data/*.json).
const SAMPLE_RANKING = [
  { name: "Proveedor Alfa S.L.", amount: 4_820_000 },
  { name: "Construcciones Beta S.A.", amount: 3_410_000 },
  { name: "Servicios Gamma S.L.", amount: 2_180_000 },
  { name: "Tecnología Delta S.A.", amount: 1_640_000 },
  { name: "Limpiezas Epsilon S.L.", amount: 980_000 },
];

const SAMPLE_CCAA = [
  { code: "MAD", v: 6 },
  { code: "CAT", v: 6 },
  { code: "AND", v: 5 },
  { code: "CVA", v: 4 },
  { code: "GAL", v: 3 },
  { code: "PVA", v: 4 },
  { code: "CYL", v: 3 },
  { code: "CLM", v: 2 },
  { code: "MUR", v: 2 },
  { code: "ARA", v: 2 },
  { code: "CAN", v: 3 },
  { code: "EXT", v: 1 },
];

const SAMPLE_SERIES = [38, 42, 40, 55, 61, 58, 67, 72, 69, 81, 88, 84];
const FILTERS = ["Todas", "Contratos menores", "Perfil contratante", "Agregaciones", "Encargos"];

const eur = new Intl.NumberFormat("es-ES", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});

export default function App() {
  const [period, setPeriod] = useState("2012–2026");
  const [source, setSource] = useState("Todas");
  const maxRank = SAMPLE_RANKING[0].amount;

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
          {["2012–2026", "2018–2026", "2022–2026"].map((p) => (
            <button key={p} aria-pressed={period === p} onClick={() => setPeriod(p)}>
              {p}
            </button>
          ))}
        </div>
      </header>

      <aside className="rail">
        <div className="filter-group">
          <h2>Fuente</h2>
          <div className="chip-list">
            {FILTERS.map((f) => (
              <button
                key={f}
                className="chip"
                aria-pressed={source === f}
                onClick={() => setSource(f)}
              >
                {f}
              </button>
            ))}
          </div>
        </div>
        <div className="filter-group">
          <h2>Territorio</h2>
          <div className="chip-list">
            {["Nacional", "Por CCAA", "Por provincia"].map((f) => (
              <button key={f} className="chip" aria-pressed={f === "Por CCAA"}>
                {f}
              </button>
            ))}
          </div>
        </div>
        <div className="filter-group">
          <h2>Indicadores</h2>
          <div className="chip-list">
            {["Concentración proveedores", "Importes bajo umbral", "Alineación política"].map((f) => (
              <button key={f} className="chip">
                {f}
              </button>
            ))}
          </div>
        </div>
      </aside>

      <main className="canvas">
        <section className="card wide">
          <div className="card-head">
            <h3>Resumen</h3>
            <span className="meta">{period} · {source} · <span className="badge">MUESTRA</span></span>
          </div>
          <div className="stat-row">
            <div className="stat">
              <div className="value">{eur.format(48_200_000_000)}</div>
              <div className="label">Importe adjudicado (acumulado)</div>
            </div>
            <div className="stat">
              <div className="value">1,284,902</div>
              <div className="label">Contratos</div>
            </div>
            <div className="stat">
              <div className="value">61,430</div>
              <div className="label">Adjudicatarios</div>
            </div>
          </div>
        </section>

        <section className="card">
          <div className="card-head">
            <h3>Gasto por CCAA</h3>
            <span className="meta">€ per cápita · normalizado</span>
          </div>
          <div className="map">
            {SAMPLE_CCAA.map((c) => (
              <div
                key={c.code}
                className="cell"
                style={{ background: `var(--seq-${c.v})` }}
                title={`${c.code}`}
              >
                {c.code}
              </div>
            ))}
          </div>
        </section>

        <section className="card">
          <div className="card-head">
            <h3>Top adjudicatarios</h3>
            <span className="meta">por importe</span>
          </div>
          <div className="ranking">
            {SAMPLE_RANKING.map((r, i) => (
              <div className="rank-row" key={r.name}>
                <span className="idx">{i + 1}</span>
                <span className="name">{r.name}</span>
                <span className="amount">{eur.format(r.amount)}</span>
                <div className="bar" style={{ width: `${(r.amount / maxRank) * 100}%` }} />
              </div>
            ))}
          </div>
        </section>

        <section className="card wide">
          <div className="card-head">
            <h3>Evolución del gasto</h3>
            <span className="meta">por año · {period}</span>
          </div>
          <div className="spark">
            {SAMPLE_SERIES.map((v, i) => (
              <div className="col" style={{ height: `${v}%` }} key={i} />
            ))}
          </div>
        </section>
      </main>

      <aside className="context">
        <h2>Contexto del dato</h2>
        <div className="kv">
          <span className="k">Fuente</span>
          <span className="v">PLACSP · datos.gob.es</span>
        </div>
        <div className="kv">
          <span className="k">Periodo</span>
          <span className="v">{period}</span>
        </div>
        <div className="kv">
          <span className="k">Cobertura</span>
          <span className="v">Menores 2018+ · Encargos 2022+</span>
        </div>
        <div className="kv">
          <span className="k">Actualización</span>
          <span className="v">Manual · por lotes</span>
        </div>
        <div className="disclaimer">
          Los indicadores (concentración, importes bajo umbral) son <strong>señales para
          investigar, no acusaciones</strong>. Correlación no implica causalidad. Consulta la
          metodología antes de extraer conclusiones.
        </div>
      </aside>

      <footer className="footer">
        <span>Datos públicos reutilizables · PLACSP</span>
        <span>·</span>
        <span>Fase 0 — sistema visual con datos de muestra</span>
      </footer>
    </div>
  );
}
