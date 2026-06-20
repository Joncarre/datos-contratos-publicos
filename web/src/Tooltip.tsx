import { useEffect, useState } from "react";

type Tip = { text: string; x: number; y: number };

// Tooltip premium global. Cualquier elemento (HTML o SVG) con atributo `data-tip="…"`
// muestra una tarjeta flotante en vez del cuadro negro nativo del navegador. Un único
// listener de mousemove lo gestiona todo; sin wiring por componente.
export function TooltipLayer() {
  const [tip, setTip] = useState<Tip | null>(null);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      const el = (e.target as Element | null)?.closest?.("[data-tip]");
      if (!el) {
        setTip((t) => (t ? null : t));
        return;
      }
      const text = el.getAttribute("data-tip") || "";
      if (!text) {
        setTip((t) => (t ? null : t));
        return;
      }
      setTip({ text, x: e.clientX, y: e.clientY });
    };
    const onLeave = () => setTip(null);
    document.addEventListener("mousemove", onMove, { passive: true });
    document.addEventListener("mouseleave", onLeave);
    window.addEventListener("scroll", onLeave, true);
    return () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseleave", onLeave);
      window.removeEventListener("scroll", onLeave, true);
    };
  }, []);

  if (!tip) return null;

  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const flipX = tip.x > vw - 300;
  const flipY = tip.y > vh - 120;
  const style: React.CSSProperties = {
    left: tip.x + (flipX ? -14 : 16),
    top: tip.y + (flipY ? -14 : 18),
    transform: `translate(${flipX ? "-100%" : "0"}, ${flipY ? "-100%" : "0"})`,
  };

  // Formato premium: "Etiqueta · Valor" o "Etiqueta: Valor" → etiqueta tenue + valor destacado.
  const m = tip.text.match(/^(.*?)(?:\s[·:]\s|:\s)(.+)$/);
  return (
    <div className="tip" style={style} role="tooltip">
      {m ? (
        <>
          <span className="tip-k">{m[1]}</span>
          <span className="tip-v">{m[2]}</span>
        </>
      ) : (
        tip.text
      )}
    </div>
  );
}
