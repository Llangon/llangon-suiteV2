import Image from "next/image";

export default function Home() {
  return (
    <main className="landing-shell">
      <section className="access-card landing-card">
        <Image src="/logo-llangon.png" width={360} height={150} alt="Llangón Asesores" priority />
        <p className="section-eyebrow">Portal de licitaciones</p>
        <h1>Información preparada para cada cliente</h1>
        <p>Accede desde el enlace personal que te ha facilitado Llangón Asesores.</p>
        <small>El acceso y las descargas quedan registrados por motivos de trazabilidad.</small>
      </section>
    </main>
  );
}
