# Streets and settlements — OpenStreetMap

The files `<uid>.json` in this folder (one per oblast, Kyiv and Sevastopol: the app's oblast uids) hold every
settlement (place = city / town / village / hamlet) and every named street of Ukraine as OpenStreetMap has them.

**© OpenStreetMap contributors.** The data is available under the
[Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/) — see
<https://www.openstreetmap.org/copyright>. These files are a derived database and are distributed under the same
licence: you may copy, distribute and adapt them as long as you credit OpenStreetMap and its contributors and share
what you derive from them under the ODbL.

Built by `scripts/build_streets.py` from the regional extracts of <https://download.openstreetmap.fr/extracts/europe/ukraine/>
(each file says which extract, `src`, and when it was built, `built`). The app credits OpenStreetMap wherever a
street or a village from these files is shown (the pin pickers of the Tactical and Light pages).
