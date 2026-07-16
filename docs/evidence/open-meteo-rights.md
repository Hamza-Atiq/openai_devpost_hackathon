# Open-Meteo usage-rights review

| Field | Review record |
| --- | --- |
| Reviewed on | 2026-07-16 |
| Reviewer | Codex, with human approval required before commercial launch |
| Intended V1 use | Public hackathon evaluation and product prototyping |
| Decision | The free API is acceptable only while CrickOps remains non-commercial and within the published limits. Attribution is mandatory. |

## Official-source findings

1. Open-Meteo's free/open-access API is limited to non-commercial use. The published limits are 600 calls per minute, 5,000 per hour, 10,000 per day, and 300,000 per month. The free service has no uptime guarantee and may block misuse.
2. Open-Meteo explicitly directs evaluation and prototyping to the free tier. This supports the hackathon deployment only while it is non-commercial and stays within the limits above.
3. API data are provided under CC BY 4.0. Wherever Open-Meteo data are displayed, CrickOps must show linked credit. Open-Meteo's example is “Weather data by Open-Meteo.com.” The attribution must not imply endorsement and must indicate material transformations where applicable; CrickOps describes its derived output as forecast-based risk guidance.
4. The data licence and API-service permission are separate. Although CC BY 4.0 permits reuse of data with attribution, Open-Meteo's free hosted API terms restrict that service to non-commercial use.
5. Before any commercial, advertising-supported, subscription, promotional, or otherwise commercial launch, the product owner must re-review the current terms and select a paid customer API plan or a legally reviewed self-hosted deployment. Paid access uses the customer endpoint and an API key; no such key may be exposed in the frontend.
6. The provider disclaims accuracy, completeness, availability, and uninterrupted provision. CrickOps therefore retains deterministic demo mode and must never present unavailable forecast data as safe.

## Required Version 1 copy

- Interface and weather panels: [Weather data by Open-Meteo.com](https://open-meteo.com/)
- Tournament export: provider name, provider URL, forecast issue/fetch time, and the same attribution text
- Repository documentation: attribution plus the non-commercial free-tier and commercial follow-up notice
- Derived risk explanation: “CrickOps transforms forecast data into planning risk guidance; it is not an official safety or weather decision.”

The canonical copy fixture is `apps/api/tests/fixtures/weather/open-meteo-attribution.json`.

## Capacity and operational controls

- Cache and batch coordinate requests where supported.
- Track minute, hour, day, and month request budgets in production observability.
- Switch to deterministic mode on provider failure or exhausted capacity; do not fabricate live results.
- Treat the free endpoint as having no availability commitment.

## Commercial follow-up gate

Commercial use is blocked until a named human owner records a new dated review of the then-current official terms, selects paid API or self-hosting, confirms upstream data-source obligations, configures the correct endpoint and secrets, and re-runs attribution and degraded-mode acceptance tests.

## Official sources reviewed

- [Open-Meteo pricing](https://open-meteo.com/en/pricing)
- [Open-Meteo terms](https://open-meteo.com/en/terms)
- [Open-Meteo licence](https://open-meteo.com/en/license)
- [Open-Meteo forecast API documentation](https://open-meteo.com/en/docs)
- [Open-Meteo geocoding API documentation](https://open-meteo.com/en/docs/geocoding-api)

