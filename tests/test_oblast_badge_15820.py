"""1.58.20 — the oblast badges and names, zoomed out.

The owner: "for the number of drones in an oblast we go by how many are currently reported within the oblast, with a
'~' to show it is an estimate"; and of the whole country on the satellite: "the oblast's name — honestly we don't need
it zoomed out, or make it more discreet: it takes all the room"."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()
I18N = open(os.path.join(ROOT, "static", "i18n.js"), encoding="utf-8").read()
SAFETY = open(os.path.join(ROOT, "docs", "SAFETY.md"), encoding="utf-8").read()


def test_the_badge_counts_what_is_reported_in_the_oblast_as_an_estimate():
    # the drones placed in each oblast, counted as the map's totals count them (each mark's own count)
    assert "OBLPLACED=pc;" in PAGE and "o[k]=(o[k]||0)+(m.count||1);" in PAGE
    assert "if(m.status||m.endedBy||m.stale||m.type!=='drones'||!m.oblast_uid) continue;" in PAGE   # 1.58.24: not a stale one
    # the larger of the two, never their sum (a channel's oblast total is often the same drones as the placed ones)
    assert "Math.max(by[k],(OBLPLACED[uid]||{})[k]||0)" in PAGE and "by[k]+(OBLPLACED" not in PAGE
    # written "~12": an estimate, and only for drones and jet drones; an outcome keeps its count
    assert "c=OBL_EST(k)?(N>1?'~'+N:''):(n>1?'×'+n:'')" in PAGE and "const OBL_EST=k=>k==='t:drones'||k==='t:jet';" in PAGE
    # the badge is drawn again when the placed ones change
    assert "JSON.stringify(OBLPLACED[u]||{})" in PAGE
    # and it no longer says "somewhere in the oblast" for drones that are placed
    assert "kinds.some(k=>OBL_EST(k)&&est(k)>by[k])?(uid==='31'?'city_now':'obl_now')" in PAGE
    for k in ("obl_est:", "obl_now:", "city_now:"):
        assert I18N.count(k) == 3, k
    assert "an estimate, not a count" in I18N
    assert "## A number of drones is an estimate, and says so (1.58.20)" in SAFETY


def test_the_oblast_names_step_back_zoomed_out():
    assert "svg.veryfar .oblbl{font-size:calc(var(--k,1)*9.5px);font-weight:700;letter-spacing:1.4px}" in PAGE
    assert "svg.tiled.veryfar .oblbl{fill-opacity:.48;" in PAGE
    # on a phone over the whole country only the lit names (a target in the oblast) stay
    assert "svg.dense #obllbl .oblbl:not(.hot){display:none}" in PAGE and "svg.classList.toggle('dense',KPX>2.2);" in PAGE
