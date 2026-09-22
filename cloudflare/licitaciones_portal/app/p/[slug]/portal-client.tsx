"use client";

import Image from "next/image";
import { FormEvent, useEffect, useState } from "react";
import { PrintButton } from "../../print-button";
import { toPortalTender, type PortalTender } from "../../portal-model";
import type { ContentBlock, TenderSection } from "../../tender-data";

type PortalFile = { id: string; name: string; extension: string; size_bytes: number };
type PortalPayload = { model: unknown; client_label: string; files: PortalFile[] };

function SourcePages({ pages = [] }: { pages?: number[] }) {
  return pages.length ? <span className="source-pages">Ficha · {pages.map((page) => `p. ${page}`).join(", ")}</span> : null;
}

function Block({ block }: { block: ContentBlock }) {
  if (block.type === "source_page") return <article className="content-card source-page-card"><h3>Contenido íntegro · página {block.page}</h3><div className="source-page-text">{block.text}</div></article>;
  if (block.type === "text") return <article className="content-card prose-card">{block.title && <h3>{block.title}</h3>}{block.paragraphs?.map((value, index) => <p key={index}>{value}</p>)}{block.bullets && <ul>{block.bullets.map((value, index) => <li key={index}>{value}</li>)}</ul>}</article>;
  if (block.type === "cards") return <div className="mini-card-grid">{block.items.map((item, index) => <article className="mini-card" key={index}><span className="mini-number">{String(index + 1).padStart(2, "0")}</span><h3>{item.title}</h3><p>{item.text}</p></article>)}</div>;
  if (block.type === "notice") return <aside className={`notice notice-${block.tone}`}><span>{block.title}</span><p>{block.text}</p></aside>;
  if (block.type === "criteria") return <article className="content-card criteria-card"><div className="criteria-head"><div><p>{block.title}</p><h3>{block.scope}</h3></div><span>{block.total}</span></div><div className="criteria-list">{block.criteria.map((item, index) => <div className="criterion" key={index}><div><h4>{item.name}</h4><p>{item.description}</p></div><strong>{item.score}</strong></div>)}</div></article>;
  return <article className="content-card table-card">{block.title && <h3>{block.title}</h3>}{block.caption && <p>{block.caption}</p>}<div className="table-scroll"><table><thead><tr>{block.columns.map((value, index) => <th key={index}>{value}</th>)}</tr></thead><tbody>{block.rows.map((row, rowIndex) => <tr key={rowIndex}>{row.map((cell, index) => <td key={index}>{cell}</td>)}</tr>)}</tbody></table></div></article>;
}

function Section({ section, index }: { section: TenderSection; index: number }) {
  return <section className={`content-section ${index % 2 ? "section-tint" : ""}`} id={section.id}><div className="section-inner"><header className="section-heading"><div><p className="section-eyebrow">{section.eyebrow}</p><h2>{section.title}</h2>{section.introduction && <p className="section-lead">{section.introduction}</p>}</div><SourcePages pages={section.sourcePages} /></header><div className="blocks">{section.blocks.map((block, blockIndex) => <Block block={block} key={blockIndex} />)}</div></div></section>;
}

function Portal({ tender, files, slug }: { tender: PortalTender; files: PortalFile[]; slug: string }) {
  const deadline = tender.deadline;
  return <main>
    <header className="site-header"><a className="brand" href="#inicio"><Image src="/logo-llangon.png" width={360} height={150} alt="Llangón Asesores" priority /></a><nav><a href="#resumen">Resumen</a><a href="#descargas">Descargas</a></nav><PrintButton /></header>
    <section className="hero" id="inicio"><div className="hero-inner"><div className="hero-copy"><p className="eyebrow">Ficha de licitación</p>{tender.recipient && <p className="recipient">Preparada para {tender.recipient}</p>}<h1>{tender.title}</h1><p className="reference">Expediente {tender.reference}</p></div><aside className="deadline-card"><span className="deadline-label">Presentación de ofertas</span><strong>{deadline.day || "—"}</strong><span className="deadline-month">{deadline.month} · {deadline.year}</span><span className="deadline-weekday">{deadline.weekday}</span><div className="deadline-time"><span>Hora límite</span><b>{deadline.time || "—"}</b></div></aside></div></section>
    {tender.highlights.length > 0 && <section className="summary-band"><div className="summary-grid">{tender.highlights.map((item, index) => <article key={index}><span>{item.label}</span><strong>{item.value}</strong><small>{item.detail}</small></article>)}</div></section>}
    <section className="confidentiality"><div><span>Información confidencial</span><p>Información de uso exclusivo para su destinatario. El acceso y las descargas se registran por motivos de trazabilidad.</p></div></section>
    {tender.details.length > 0 && <section className="content-section" id="resumen"><div className="section-inner"><header className="section-heading"><div><p className="section-eyebrow">Resumen</p><h2>Características de la licitación</h2></div><SourcePages pages={[1]} /></header><div className="detail-grid">{tender.details.map((item, index) => <article className="detail-item" key={index}><span>{item.label}</span><strong>{item.value}</strong>{item.note && <p>{item.note}</p>}</article>)}</div></div></section>}
    {tender.sections.map((section, index) => <Section section={section} index={index} key={section.id} />)}
    <section className="downloads-section" id="descargas"><div className="section-inner"><header className="section-heading"><div><p className="section-eyebrow">Documentación</p><h2>Descargas</h2></div><span className="download-count">{files.length} documentos</span></header><div className="download-list">{files.map((file) => <article className="download-card" key={file.id}><span className="file-type">{file.extension || "FILE"}</span><div><h3>{file.name}</h3><small>{Math.max(1, Math.round(file.size_bytes / 1024))} KB</small></div><a className="primary-action" href={`/api/portal/${encodeURIComponent(slug)}/files/${encodeURIComponent(file.id)}`}>Descargar</a></article>)}</div></div></section>
    <footer><Image src="/logo-llangon.png" width={360} height={150} alt="Llangón Asesores" /><p>Información preparada exclusivamente para {tender.recipient || "su destinatario"}.</p><span>info@llangon.com · ASESORES LLANGÓN, S.L.</span></footer>
  </main>;
}

export function PortalClient({ slug }: { slug: string }) {
  const [payload, setPayload] = useState<PortalPayload | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const load = async () => { const response = await fetch(`/api/portal/${encodeURIComponent(slug)}`, { cache: "no-store" }); if (response.ok) setPayload(await response.json()); setLoading(false); };
  useEffect(() => {
    let active = true;
    fetch(`/api/portal/${encodeURIComponent(slug)}`, { cache: "no-store" })
      .then(async (response) => { if (active && response.ok) setPayload(await response.json()); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [slug]);
  const submit = async (event: FormEvent) => { event.preventDefault(); setError(""); setLoading(true); const response = await fetch(`/api/portal/${encodeURIComponent(slug)}/access`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }) }); const result = await response.json().catch(() => ({})); if (!response.ok) { setError(result.error || "No se pudo validar el acceso."); setLoading(false); return; } await load(); };
  if (payload) return <Portal tender={toPortalTender(payload.model)} files={payload.files} slug={slug} />;
  return <main className="landing-shell"><form className="access-card" onSubmit={submit}><Image src="/logo-llangon.png" width={360} height={150} alt="Llangón Asesores" priority /><p className="section-eyebrow">Acceso personal</p><h1>Consulta de licitación</h1><p>Introduce la palabra clave que has recibido.</p><label>Palabra clave<input value={code} onChange={(event) => setCode(event.target.value)} autoComplete="one-time-code" autoCapitalize="characters" required /></label>{error && <p className="access-error" role="alert">{error}</p>}<button className="primary-action" disabled={loading}>{loading ? "Comprobando…" : "Acceder"}</button><small>El acceso y las descargas quedarán registrados.</small></form></main>;
}
