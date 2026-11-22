# ORCA: An Ocean and Coastal Response Assistant for Marine Information and Advisory Support

**Bhavneet Rajput** — S24CSEU0889  
**Aryan** — S24CSEU0912  
**Devashish Anand** — S24CSEU0123

## Abstract

This paper presents ORCA, a browser-based ocean information assistant and location-aware marine advisory prototype. ORCA combines a curated, rule-matched ocean-science question-answering component with a Flask web service that parses marine intents, locations, coordinates, and forecast time windows. For a located advisory, the application retrieves marine and weather forecasts from Open-Meteo, obtains sea-surface-temperature (SST) and chlorophyll observations from NOAA CoastWatch ERDDAP, estimates a potential fishing-zone (PFZ) candidate, and calculates distances to configured illustrative coastal boundaries. The system reports unavailable live data rather than substituting synthetic observations. A responsive JavaScript interface displays answers and data-source notices, and a dedicated prompt laboratory compares zero-shot and few-shot prompts with Gemini 2.5 Flash. Automated tests cover the principal API, prompt evidence, parsing, forecast summarization, provider parsing, and geographic-analysis paths. ORCA is an educational prototype; its heuristic thresholds, candidate-selection method, and boundary definitions are not validated for operational navigation, fishing, or safety decisions.

**Index Terms—** ocean information system, marine advisory, potential fishing zone, geospatial analysis, Flask, NOAA ERDDAP, prompt engineering, Gemini.

## I. Introduction

Ocean and coastal information is distributed across general educational resources, marine forecasts, and geospatial observation services. ORCA (Ocean and Coastal Response Assistant) explores a single conversational interface for a subset of these needs: answering common ocean-science questions and returning location-dependent marine summaries.

The project has two main modes. General questions are answered from a finite curated knowledge base and do not require a location. Marine advisory requests use a supported coastal place or latitude/longitude coordinates. When a request requires local information but provides no location, ORCA asks the user to supply one rather than silently selecting a default.

The objective of this project is to demonstrate an end-to-end browser-to-backend workflow that combines query interpretation, external marine data retrieval, simple geospatial calculations, and explicit data provenance. The implementation is a prototype, not an official source of warnings or operational advice.

## II. Related Work

ORCA builds on existing marine and meteorological data services rather than developing forecast or satellite products. Open-Meteo exposes marine variables such as wave height and sea-surface temperature alongside forecast variables including wind, gusts, precipitation, and weather codes [1]. ORCA requests these services for a user-selected location and aligns their hourly values to summarize a requested time window.

For ocean observations, NOAA CoastWatch ERDDAP provides gridded datasets that can be queried programmatically. ORCA uses near-real-time NOAA SST and chlorophyll products and attempts a gap-filled chlorophyll product when near-real-time chlorophyll samples are unavailable [2]. The application's rule-based question answering and intent parsing provide a lightweight alternative to an open-ended language model: supported questions are answered from fixed content, while unsupported topics receive capability guidance.

Unlike an operational marine service, ORCA does not issue official warnings or establish validated fishing recommendations. It is an integration and interface prototype whose outputs depend on the availability, coverage, age, and resolution of external datasets.

## III. Dataset

ORCA does not train a statistical model and does not use a fixed benchmark dataset. Its input data and knowledge sources are:

1. **Curated ocean knowledge:** Twelve topic patterns map common explanatory questions to fixed responses, covering topics such as tides, currents, waves, marine life, coral reefs, salinity, tsunamis, acidification, pollution, phytoplankton, sea-level rise, and general ocean concepts.
2. **Marine and weather forecasts:** Hourly marine and forecast values are requested from the Open-Meteo Marine and Forecast APIs [1]. The fields used include wave height and period, swell height, sea-surface temperature, wind speed and gusts, precipitation, weather code, and CAPE. The service data are external and can be unavailable for a location or request.
3. **Satellite observations:** The application queries NOAA CoastWatch ERDDAP for near-real-time SST and chlorophyll observations. If the near-real-time chlorophyll query has no usable samples, it retries using a gap-filled chlorophyll dataset [2]. The data are cached for up to 30 minutes. Observations older than 21 days are not used to return a current PFZ estimate.
4. **Configured geographic data:** A list of supported place aliases and coordinates, illustrative boundary polylines/circles, and application thresholds are stored in the project configuration. These are configuration inputs, not authoritative maritime boundary data.
5. **Test fixtures:** Automated tests use controlled forecast and satellite-response fixtures, including simulated network failures. These fixtures verify application behavior and are not scientific observations.

When a live provider fails or returns no usable values, the application reports the data as unavailable. It does not replace missing weather or satellite observations with generated values. This distinction is included in the response metadata and user-facing notices.

## IV. Methodology

### A. System Architecture

The application uses a Python/Flask backend and an HTML/CSS/JavaScript client. The browser sends a JSON query to `/api/analyze`; Flask validates the request and delegates parsing and analysis to the project modules. The main components are `main.py` for API routing and summaries, `intent.py` for language/intent/location/time parsing, `ocean_knowledge.py` for curated answers, `data_sources.py` for external APIs, `geo_utils.py` for geographic calculations, and `config.py` for locations, thresholds, and illustrative boundaries.

The request flow is:

1. Parse the user's text for a supported general question, marine intent, place or coordinates, and time cue.
2. Return a curated answer for a recognized ocean-knowledge question without requiring location.
3. For an unsupported or unrecognized intent, return capability guidance. For a local request without location, ask for a supported coastal place or coordinates.
4. For a located advisory, query the marine and weather services and select forecast values corresponding to the requested day and time of day.
5. For PFZ requests, retrieve NOAA SST and chlorophyll grids, pair chlorophyll observations with geographically nearby SST observations, filter invalid or stale values, and rank the remaining candidates.
6. Calculate approximate distances to the configured geographic features and return a structured JSON response with source, availability, timestamp, and prototype caveats.

### B. Forecast Summary and Condition Category

For the selected forecast window, the system summarizes maximum wave height and gust, mean wind, mean wave period and SST, and maximum precipitation. The status rule is threshold-based:

- **DANGER:** wave height is at least 3.0 m or gust is at least 55 km/h.
- **CAUTION:** otherwise, wave height is at least 2.0 m or gust is at least 40 km/h.
- **SAFE:** neither caution nor danger threshold is reached.
- **UNKNOWN:** no usable wave or gust values are available.

The service also includes forecast-derived high-wave, strong-gust, and thunderstorm signals. These thresholds and signals are demonstration logic, not official marine safety criteria or warnings.

### C. PFZ Candidate Estimation

For a selected location, the satellite provider requests chlorophyll and SST samples within a configured search radius. Each chlorophyll sample is paired with its nearest SST sample if that sample is within 45 km. Candidates must be within the configured radius and have positive chlorophyll and SST values. The application normalizes the logarithm of chlorophyll concentration across the candidates and selects the highest-scoring candidate, using distance as a tie-breaker. It reports the candidate coordinates, approximate distance and direction, observed values and date, and an estimated travel time based on a configured vessel speed.

This procedure is a simple demonstration heuristic. It is not a validated oceanographic PFZ model and does not establish that a location is suitable for fishing.

### D. Geographic Distance and Interface

Distances and bearings are computed from the user's location using geographic utilities. Boundary proximity is calculated against configured polylines or circles; these geometries are illustrative and are explicitly described as approximate. The responsive chat interface sends requests asynchronously and renders answers, advisory summaries, and source/availability notes.

### E. Prompt-Engineering Method

A separate `/prompt-lab` interface allows evaluators to test zero-shot and few-shot prompts. The Gemini integration uses the REST API for Gemini 2.5 Flash and reads `GEMINI_API_KEY` or `GOOGLE_API_KEY` only from the server environment. The browser never receives or stores an API key.

Three prompt versions are recorded. Version 1 establishes the ocean-assistant role. Version 2 adds structured sections and explicit safety constraints. Version 3 adds few-shot examples, instruction-hierarchy language, user-language preservation, uncertainty handling, and prompt-injection resistance.

The final system prompt defines an assistant role, permitted task, response structure, and safety rules. It separates retrieved context from the user's question and warns the model not to invent live observations or official advisories. Two few-shot examples demonstrate allowed ocean explanations and refusal of an instruction-overrides-safety request. Zero-shot mode applies the same constraints without those examples.

The iteration log and a 12-row test table are exposed through `/api/prompt-engineering` and in the browser. Test inputs cover normal ocean questions, location and coordinate edge cases, and invalid or adversarial requests. Adversarial tests check that the model does not reveal hidden instructions, fabricate official warnings, approve restricted-area entry, or disable safety constraints.

## V. Results

Automated regression tests were run using the project's pytest suite. The tests cover the homepage and API validation; twelve curated ocean questions; prompt-lab routing and evidence; zero-shot and few-shot prompt construction; missing-location behavior; named and coordinate-based locations; forecast time-window selection and condition thresholds; weather-provider failure handling; NOAA SST/chlorophyll CSV parsing and gap-filled chlorophyll fallback; PFZ candidate selection; and approximate boundary calculations.

The tests demonstrate expected software behavior with deterministic fixtures. In particular, they verify that a simulated network failure produces unavailable weather rather than synthetic forecast values, and that a current PFZ candidate is derived from supplied observed chlorophyll and SST samples. These results validate implementation paths, not forecast accuracy, satellite-product quality, or real-world advisory performance. No field trial, user study, or scientific comparison against an operational PFZ product was conducted.

## VI. Discussion

The main contribution of ORCA is the integration of a conversational interface with rule-based knowledge lookup, forecast APIs, satellite observations, and geographic summaries. Requiring a location for local requests avoids misleading default-location behavior, while reporting data availability and provenance helps distinguish live observations from unavailable data.

Several limitations constrain interpretation. The general knowledge base is finite and primarily English-language. Forecast condition categories use unvalidated fixed thresholds. The PFZ ranking is a simplified chlorophyll-based heuristic and does not account for all oceanographic or fisheries factors. External data can be missing, spatially coarse, or delayed despite recency checks. Configured boundaries are approximate and must not be used for legal or navigational decisions. The application also calculates several advisory summaries together for a located request, even when the query asks for only one feature. Gemini results depend on API availability and model behavior, and a live key must be supplied to the server for generation.

Future work should evaluate the system with domain experts and representative coastal locations; use authoritative, validated boundary datasets; validate safety rules with relevant authorities; improve multilingual coverage and intent routing; and compare PFZ estimates against an established scientific or operational reference. The system should remain clearly identified as a prototype until these evaluations are completed.

## VII. Conclusion

This paper described ORCA, a browser-based prototype for curated ocean-science questions and location-aware marine summaries. The system connects a Flask API and chat interface to Open-Meteo forecasts and NOAA CoastWatch SST/chlorophyll observations, and includes forecast categorization, a heuristic PFZ candidate estimate, and illustrative boundary-distance calculations. The project tests pass for the covered software behaviors, but they do not establish scientific or operational validity. ORCA should therefore be used for educational demonstration only, not as a substitute for official marine warnings, navigation information, or validated fishing guidance.

## References

[1] Open-Meteo, “Weather API and Marine API.” [Online]. Available: https://open-meteo.com/en/docs and https://open-meteo.com/en/docs/marine-weather-api

[2] NOAA CoastWatch, “ERDDAP data server.” [Online]. Available: https://coastwatch.noaa.gov/erddap/
