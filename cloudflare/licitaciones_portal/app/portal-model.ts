import type { Detail, TenderSection } from "./tender-data";

type UnknownRecord = Record<string, unknown>;

export type PortalDownload = {
  name: string;
  type: string;
  size: string;
  description: string;
};

export type PortalTender = {
  recipient: string;
  reference: string;
  title: string;
  submissionChannel: string;
  tenderUrl: string;
  deadline: { day: string; month: string; year: string; weekday: string; time: string };
  highlights: Array<{ label: string; value: string; detail: string }>;
  details: Detail[];
  sections: TenderSection[];
  downloads: PortalDownload[];
};

function record(value: unknown): UnknownRecord {
  return value && typeof value === "object" && !Array.isArray(value) ? value as UnknownRecord : {};
}

function text(value: unknown): string {
  return value == null ? "" : String(value);
}

function array<T>(value: unknown): T[] {
  return Array.isArray(value) ? value as T[] : [];
}

/** Adapta tanto el piloto como el JSON que genera y audita la suite. */
export function toPortalTender(input: unknown): PortalTender {
  const root = record(input);
  const tender = record(root.tender ?? root);
  const deadline = record(tender.deadline);
  const rawDownloads = array<UnknownRecord>(root.downloads ?? tender.downloads);
  return {
    recipient: text(tender.recipient),
    reference: text(tender.reference),
    title: text(tender.title) || "Licitación",
    submissionChannel: text(tender.submissionChannel),
    tenderUrl: text(tender.tenderUrl ?? tender.tender_url),
    deadline: {
      day: text(deadline.day),
      month: text(deadline.month),
      year: text(deadline.year),
      weekday: text(deadline.weekday),
      time: text(deadline.time),
    },
    highlights: array<PortalTender["highlights"][number]>(tender.highlights),
    details: array<Detail>(tender.details),
    sections: array<TenderSection>(root.sections ?? tender.sections),
    downloads: rawDownloads.map((file) => ({
      name: text(file.name),
      type: text(file.type ?? file.extension) || "FICHERO",
      size: text(file.size ?? file.size_human),
      description: text(file.description) || "Documento incluido en la licitación.",
    })),
  };
}
