import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://licitaciones.llangon.com"),
  title: "Portal de licitaciones | Llangón Asesores",
  description: "Información completa y documentación de licitaciones preparada por Llangón Asesores.",
  robots: { index: false, follow: false },
  icons: { icon: "/logo-llangon.png" },
  openGraph: {
    title: "Portal de licitaciones | Llangón Asesores",
    description: "Información completa y documentación de licitaciones preparada por Llangón Asesores.",
    type: "website",
    images: [{ url: "/og.png", width: 1729, height: 910, alt: "Portal de licitaciones de Llangón Asesores" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Portal de licitaciones | Llangón Asesores",
    description: "Información completa y documentación de licitaciones preparada por Llangón Asesores.",
    images: ["/og.png"],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
