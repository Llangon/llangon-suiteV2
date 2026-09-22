"use client";

export function PrintButton() {
  return (
    <button className="print-button" type="button" onClick={() => window.print()}>
      Imprimir ficha
    </button>
  );
}
