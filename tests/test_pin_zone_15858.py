"""1.58.58 — each pin's own near zone, set from its sheet on the tutorial's third screen.

The owner: "we need a way to set the pins' radius, as in the tutorial" — and his pick: one radius a pin.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


PAGE, I18N, LIGHT = _read("static", "kyiv.html"), _read("static", "i18n.js"), _read("static", "light.html")


def _between(a, b, s=PAGE):
    i = s.index(a)
    return s[i:s.index(b, i)]


def test_the_radius_is_the_pins_own_and_stays_on_the_phone():
    assert "function pinR(p){ return p&&NEAR_RS.includes(p.r)?p.r:NEAR_DEF; }" in PAGE
    assert "var NEAR_R=pinR(HOME);" in PAGE
    # the pin on screen sets it, each time it changes
    assert "ACTIVE=id; HOME=SLOTS[id]||null; saveSlots(); nearSync();" in PAGE
    # a copy of the place (a list's entry is shared), with its radius: the one given, else the pin's own — moved, it keeps it
    assert "SLOTS[id]=place?Object.assign({},place,{r:NEAR_RS.includes(place.r)?place.r:pinR(SLOTS[id])}):null;" in PAGE
    setr = _between("function setNearR(r,slot){", "document.querySelectorAll('#nearrr [data-nr]')")
    # the others keep theirs: one with none is given the last chosen first, then the default moves
    assert setr.index("SLOTS[id].r=NEAR_DEF") < setr.index("NEAR_DEF=r")
    assert "if(SLOTS[slot]) SLOTS[slot].r=r;" in setr and "saveSlots()" in setr
    # never sent: the radius is in the pins' own record (localStorage), and no request carries a pin
    for body in re.findall(r"body:JSON\.stringify\((\{[^)]*\})\)", PAGE):
        assert "SLOTS" not in body and "HOME" not in body


def test_the_pins_sheet_opens_the_tutorials_third_screen_for_that_pin():
    assert '<button type="button" class="hspick hszone" id="hszone">' in PAGE and "$('hszone').onclick=zoneOpen;" in PAGE
    assert "r:pinR(SLOTS[id])};" in PAGE                                     # the sheet starts from the pin's own
    op = _between("function zoneOpen(){", "function zoneClose(")
    assert "P.name=$('homen').value; ZONE_VB={...VB};" in op                 # the name typed, and the map, kept
    assert "SETUP={step:3,zone:true,slot:P.slot,place:P.place,r:P.r,msg:''};" in op and "setFull(true,true)" in op
    cl = _between("function zoneClose(keep){", "function hsZoneLbl(")
    assert "if(keep&&HS_PEND) HS_PEND.r=s.r;" in cl and "Object.assign(VB,ZONE_VB)" in cl and "$('homesheet').classList.add('show')" in cl
    # "Back" changes nothing, "Done" gives the sheet the radius, "Save the pin" keeps it
    assert "if(SETUP.zone) zoneClose(false);" in PAGE and "if(s.zone) zoneClose(true);" in PAGE
    assert "if(P.r!==pinR(SLOTS[slot])) setNearR(P.r,slot);" in PAGE
    # the zone being chosen is drawn around that pin, at the radius on screen
    dz = _between("function drawZones(){", "// The conditional ETA")
    assert "const zp=SETUP&&SETUP.zone?SETUP.place:HOME, zs=SETUP&&SETUP.zone?[[SETUP.r,'near'],...ZONES.slice(1)]:ZONES;" in dz
    assert "if(SETUP&&SETUP.zone){ SETUP.r=+b.dataset.nr; drawZones(); } else setNearR(b.dataset.nr);" in PAGE
    assert "$('sustep').textContent=s.zone?(($('homen').value||'').trim()||pinLabel(s.slot)):t('su_step',s.step,3);" in PAGE


def test_the_bell_row_is_the_pin_on_screens_and_light_reads_the_pins_own():
    assert '<span class="ml" id="nzl" data-t="nz_r">' in PAGE
    assert "$('nzl').textContent=HOME?t('nz_r_pin',pinLabel(ACTIVE)):t('nz_r');" in PAGE
    for k in ("nz_r_pin", "hs_zone_b"):
        assert len(re.findall(r"(?<![A-Za-z_])" + k + r":'", I18N)) == 3, k
    assert "const nearR=()=>{ const r=(place()||{}).r; return [10,15,20].includes(r)?r:NEAR_D; };" in LIGHT
