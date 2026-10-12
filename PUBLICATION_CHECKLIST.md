# Open-science publication plan — Geodetic & Elevation Data Toolkit

## Which platform should hold the software?

**Recherche Data Gouv explicitly recommends depositing research source code/software in HAL or a code forge archived by Software Heritage.** Its guidance strongly discourages depositing source code *alone*, without accompanying research data, in the Recherche Data Gouv repository. Consult the institutional data steward before treating the repository as the software's primary publication destination.

Official reference: https://recherche.data.gouv.fr/en/guide/where-to-deposit-source-codes-and-softwares

Recommended publication chain:

1. Maintain development, versioned tags, documentation, issues and citations on **GitHub**.
2. Once third-party rights have been confirmed, make an approved, complete source snapshot public and archive it through **Software Heritage**; consider the appropriate **HAL software deposit** workflow.
3. Record the persistent source identifier (SWHID) and/or HAL identifier in the README and citation metadata, rather than inventing identifiers.
4. Use **Recherche Data Gouv** for relevant **research data** (for example, reproducibility test datasets and metadata) with source-code and software identifiers cross-linked. Confirm permissions and the right institutional collection.
5. If a DOI is needed for a standalone software release, assess an appropriate software archive and avoid duplicate DOI records for the exact same research object.

## Required quality gates

- Confirm permission to redistribute `data/RAF20.tac` and each institutional logo/figure, or remove them from public archives and provide a legal user-side acquisition workflow.
- Verify CeCILL-B notice, contributors' approval, authorship, version, source identifier, and explicit software citation.
- Run a test matrix for AOI raster geoid grids, point/CSV heights, ellipsoidal ↔ compatible physical heights, source DEM retrieval, and GPS time.
- Independently validate known geographic control points and metadata for RAF20, EGM96, EGM2008, and custom grids (where supported).
- Verify the browser presentation at mobile and desktop sizes; test uploaded files and georeferenced result downloads.
- Run security and resource tests for hosted geospatial processing (geometry limits, pixel quotas, upload limits, extraction safety, memory/time quotas, rate controls and cleanup).
- Do not call the hosted preview a fully functional public version while raster or DEM processing remains disabled.
- Prepare sample inputs, output data dictionary, software citation (CITATION.cff and BibTeX), release notes, and long-term archived metadata.
- Decide whether the actual research data will be deposited in Recherche Data Gouv with GitHub/HAL/Software Heritage citations, following the hosting institution's rules.

**Status (2026-10-12):** Documentation and hosted preview available. First bounded RAF20 point/CSV API staged on `web-deployment`, feature flag off by default; test and validation pending. Full online scientific processing not publicly enabled.

## Example scientific metadata (adapt before deposit)

**Title:** Geodetic & Elevation Data Toolkit: validated examples of geoid separation, DEM height conversion, and GNSS/LiDAR GPS-time interpretation.

**Software creator:** Islam Koa. Supervisors acknowledged: Alain Recking; Laurent Borgniet.

**Associated resources:** GitHub source code; versioned software source identifier (when archived); web demo (where appropriate); datasets with provenance, horizontal/vertical CRS, units, sensor origin and redistribution license.

For current guidance see:
- https://recherche.data.gouv.fr/en/guide/where-to-deposit-source-codes-and-softwares
- https://recherche.data.gouv.fr/fr/guide/avant-de-deposer
