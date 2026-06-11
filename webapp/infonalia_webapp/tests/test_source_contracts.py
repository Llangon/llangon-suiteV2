from __future__ import annotations

from collections.abc import Iterable

from webapp.infonalia_webapp.core.models import LicitacionCandidate, LicitacionNormalized
from webapp.infonalia_webapp.core.source_contracts import LicitationSource


class FakeLicitationSource:
    name = "fake_source"

    def fetch_candidates(self, *args: object, **kwargs: object) -> Iterable[LicitacionCandidate]:
        return [
            LicitacionCandidate(
                source_name=self.name,
                raw_payload={"titulo": "Contrato de prueba"},
                external_id="fake-1",
            )
        ]

    def normalize(self, candidate: LicitacionCandidate) -> LicitacionNormalized:
        return LicitacionNormalized(
            source_name=candidate.source_name,
            titulo=str(candidate.raw_payload["titulo"]),
            external_id=candidate.external_id,
            raw_payload=candidate.raw_payload,
        )


def test_licitation_source_protocol_can_be_used_with_fake_source() -> None:
    source: LicitationSource = FakeLicitationSource()

    candidates = list(source.fetch_candidates())
    normalized = source.normalize(candidates[0])

    assert isinstance(source, LicitationSource)
    assert source.name == "fake_source"
    assert candidates[0].external_id == "fake-1"
    assert normalized.titulo == "Contrato de prueba"

