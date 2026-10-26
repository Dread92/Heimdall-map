"""1.58.56 — the first run in three steps, the near zone chosen, the approach signal.

A reader, after his first minutes with the app on a phone: "a banner with the current situation and an invitation to place
a marker occupied almost the entire screen … there were difficulties placing the marker … When activating the app, the
user must complete three steps: select a language; place a marker on the tactical map, at any zoom; select a minimap with
a custom tracking zone. I propose increasing the minimum tracking zone to 15 km, and eventually to 20 km … a signal when
entering the zones: the closer, the more alarming; in the very last zone periodic, the frequency increasing as it
approaches." The owner's picks: the three steps; the zone 10, 15 or 20 km, 15 unless chosen; the signal by the distance
reported. Polish and Romanian: not now.
"""
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


PAGE, I18N, LIGHT, BOT = _read("static", "kyiv.html"), _read("static", "i18n.js"), _read("static", "light.html"), _read("app", "tgbot.py")


def _between(a, b, s=PAGE):
    i = s.index(a)
    return s[i:s.index(b, i)]


# ---- the three steps ---------------------------------------------------------------------------------------------------
def test_the_notice_is_step_one_and_the_map_steps_follow_once():
    assert "function setupWanted(){ let d=false; try{ d=localStorage.getItem('setup_done')==='1'; }catch(e){} return !d&&!SLOT_IDS.some(id=>SLOTS[id]); }" in PAGE
    step = _between("function discStep(){", "function setupStart(){")
    assert "st.textContent=t('su_step',1,3)" in step and "t(su?'d_ok_next':'d_ok')" in step
    assert "h.closest('label').hidden=su" in step                     # the place is step 2, not a line of the notice
    assert ".dset label[hidden]{display:none}" in PAGE                # (.dset label is a flex box: [hidden] alone lost)
    assert "$('disc').hidden=seen; discStep();" in PAGE and "if(setupWanted()) setupStart(); };" in PAGE
    start = _between("function setupStart(){", "function setupEnd(")
    assert "if(!MAP){ setTimeout(setupStart,300); return; }" in start
    assert "document.body.classList.add('setup'); setFull(true,true);" in start   # the map alone, the browser as it is
    end = _between("function setupEnd(done){", "function setupPaint(){")
    assert "localStorage.setItem('setup_done','1')" in end and "setFull(false)" in end
    assert "if(done&&SLOTS[s.slot]) notify('📍 '+slotName(s.slot),t('su_done_b',NEAR_R),'end');" in end
    # "Skip" ends it; "Back" from step 3; "Next" only once a pin is on the map
    assert "if(SETUP.step===2) setupEnd(false); else { SETUP.step=2; setupPaint(); }" in PAGE
    assert "n.disabled=two&&!p;" in PAGE and "if(!SLOTS[s.slot]) return; s.step=3;" in PAGE
    # var: useSlot runs before the setup's own lines do, and asks for it
    assert "var SETUP=null;" in PAGE and "if(typeof setupPaint==='function') setupPaint(); }" in PAGE


def test_step_two_a_tap_puts_the_pin_at_any_zoom_and_another_moves_it():
    up = _between("wrap.addEventListener('pointerup',", "wrap.addEventListener('pointercancel'")
    assert up.index("if(SETUP&&tap){ if(SETUP.step===2) setupDrop(e.clientX,e.clientY); return; }") < up.index("if(PIN_ARM&&tap)")
    assert "if(!downMk&&!PIN_ARM&&!SETUP&&Object.keys(touches).length===1)" in PAGE    # no press-and-hold pin meanwhile
    drop = _between("function setupDrop(px,py){", "$('suskip').onclick")
    assert "setSlot(s.slot,keep?Object.assign({lon,lat},keep):{lon,lat,dropped:true});" in drop
    assert "setView" not in drop                                       # the view stays as the reader zoomed it
    assert "if(!g||SETUP) return;" in PAGE                             # a tap on the pin is not its sheet meanwhile
    # GPS and an address are the other two ways; nothing of the place leaves the phone
    gps = _between("$('sugps').onclick=", "// ---- 1.58.56: the approach signal")
    assert "navigator.geolocation.getCurrentPosition" in gps and "fetch(" not in gps
    assert "openPinSheet(s.slot,'new').then(()=>$('homefind').onclick())" in PAGE
    assert "if(FULL&&!noFs&&el.requestFullscreen" in PAGE


def test_step_three_the_zone_on_the_map():
    paint = _between("function setupPaint(){", "function setupView(")
    assert "NEAR_RS.map(r=>`<button type=\"button\" data-nr=\"${r}\"" in paint
    view = _between("function setupView(wKm){", "function setupDrop(")
    assert "(2*(SETUP.zone?SETUP.r:NEAR_R)/0.55)" in view                # 1.58.58: or the pin's zone being chosen and "VB.y=y-((y0+y1)/2-r.top)*k" in view
    assert "else setNearR(b.dataset.nr); setupPaint(); setupView(); };" in PAGE


# ---- the near zone -----------------------------------------------------------------------------------------------------
def test_the_near_zone_is_the_readers_and_used_everywhere_the_ten_was():
    # 1.58.58: each pin's own (tests/test_pin_zone_15858.py); near_r is the last one chosen, 15 unless chosen
    assert "var NEAR_RS=[10,15,20], NEAR_DEF=15;" in PAGE
    assert "const r=+localStorage.getItem('near_r'); if(NEAR_RS.includes(r)) NEAR_DEF=r;" in PAGE
    setr = _between("function setNearR(r,slot){", "document.querySelectorAll('#nearrr [data-nr]')")
    assert "nearSync()" in setr and "localStorage.setItem('near_r',String(r))" in setr and "drawZones()" in setr
    assert "function nearSync(){ NEAR_R=pinR(HOME); try{ ZONES[0][0]=NEAR_R; }catch(e){}" in PAGE
    for s in ("const ZONES=[[NEAR_R,'near'],[30,'approach'],[60,'observe']];",
              "near:dist<NEAR_R||imm,inbound:false", "near:dist<NEAR_R||imm,inbound:named",
              "if(d<=NEAR_R) return {rank:3,level:3,why:'near'};",
              "r.d<=NEAR_R?'near':r.d<=30?'approach'", "near:t('lt_z_near',NEAR_R)",
              "if(HOME&&live.some(r=>r.d<=NEAR_R)) lv=3;", "(top.d<=NEAR_R||here?' near':'')",
              "t('z_'+z,NEAR_R)", "t('lb_nearhome',esc(homeName()),NEAR_R)", "t('n_home_b',NEAR_R)"):
        assert s in PAGE, s
    assert not re.search(r"\b(?:d|dist|r\.d|top\.d)\s*<=?\s*10\b", PAGE)
    # Light reads the same choice; the bot keeps its own 10 km (the owner's pick, 1.58.40)
    assert "if([10,15,20].includes(r)) NEAR_D=r;" in LIGHT and "const zoneOf=d=>d<=nearR()?'near':d<=30?'approach':null;" in LIGHT
    assert "t('lt_z_'+zone,nearR())" in LIGHT and "k===nearR()?' r10':''" in LIGHT
    assert "NEAR_KM = 10.0" in BOT
    # a setting, never a place: carried like the others in a link to the new address, never sent to the server
    assert "'sup_never','near_r','beep'];" in PAGE
    for body in re.findall(r"body:JSON\.stringify\((\{[^)]*\})\)", PAGE):
        assert "NEAR_R" not in body and "near_r" not in body


def test_the_texts_say_the_chosen_km_in_three_languages():
    for k in ("lt_z_near", "z_near", "n_home_b", "snd_why"):
        vals = re.findall(r"(?<![A-Za-z_])" + k + r":'((?:[^'\\]|\\.)*)'", I18N)
        assert len(vals) == 3 and all("{0}" in v and "10 " not in v for v in vals), k
    vals = re.findall(r"(?<![A-Za-z_])lb_nearhome:'((?:[^'\\]|\\.)*)'", I18N)
    assert len(vals) == 3 and all("{1}" in v and "{0}" in v for v in vals)
    for k in ("su_step", "d_ok_next", "su2_h", "su2_t_touch", "su2_t_mouse", "su2_set", "su2_priv", "su_skip", "su_next", "su_back",
              "su_done", "su3_h", "su3_t", "su3_why", "su_done_b", "nz_r", "nz_why", "bp_lbl", "bp_b", "bp_chip", "bp_off"):
        assert len(re.findall(r"(?<![A-Za-z_])" + k + r":'", I18N)) == 3, k
    # the step counter is "2/3": the Cyrillic "З" in "2 З 3" read as a 3 in the mono font
    assert "su_step:'КРОК {0}/{1}'" in I18N
    assert "$('sndw').textContent=t('snd_why',NEAR_R);" in PAGE and 'id="sndw"' in PAGE


# ---- the approach signal -----------------------------------------------------------------------------------------------
def test_the_signal_follows_the_reported_distance_and_nothing_else():
    assert "const BEEP_FRESH_MIN=5, BEEP_MUTE=new Set(); let BEEP_ON=true, BEEP_T=null;" in PAGE
    assert "BEEP_ON=localStorage.getItem('beep')!=='0';" in PAGE                   # on unless switched off
    rows = _between("function beepRows(){", "function beepLoop(){")
    for s in ("!r.imm", "!r.vague", "!m.stale", "!m.status", "!m.endedBy", "!m.held", "r.d<=NEAR_R", "agoMin(m.pos_ts||m.ts)<=BEEP_FRESH_MIN"):
        assert s in rows, s
    assert "if(!HOME) return [];" in rows
    # r.d is where the post put it: posOf moves a mark only with the estimate, which is off for everybody
    assert "let ESTIMATE=false;" in PAGE
    loop = _between("function beepLoop(){", "$('beepchip').onclick")
    assert "const on=!!r&&BEEP_ON&&soundOn&&sndVol>0&&!SETUP;" in loop
    assert "beep('tick',1.5); BEEP_T=setTimeout(beepLoop,beepEvery(r.d)*1000);" in loop
    assert "for(const k of [...BEEP_MUTE]) if(!keys.has(k)) BEEP_MUTE.delete(k);" in loop   # a return ticks again
    assert "$('beepchip').onclick=()=>{ for(const r of beepRows()) BEEP_MUTE.add(trackKey(r.m)); beepLoop(); };" in PAGE
    assert "kind==='tick'?[[1250,.07]]" in PAGE
    # every 8 s at the zone's edge, every second at the pin — whatever the zone
    every = re.search(r"const beepEvery=(d=>[^;]*);", PAGE).group(1)
    js = (f"const NEAR_RS=[10,15,20];let NEAR_R;const beepEvery={every};const out=[];"
          "for(const z of NEAR_RS){NEAR_R=z;out.push([beepEvery(0),beepEvery(z/2),beepEvery(z),beepEvery(z+5)]);}console.log(JSON.stringify(out));")
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout
    for row in __import__("json").loads(out):
        assert row[0] == 1 and row[2] == 8 and row[3] == 8 and abs(row[1] - 4.5) < 1e-9


def test_its_switch_and_its_chip():
    assert '<button class="mi tg on" id="beepbtn" type="button"><span class="lb" data-t="bp_lbl">' in PAGE
    assert "localStorage.setItem('beep',BEEP_ON?'1':'0')" in PAGE
    assert '<button type="button" id="beepchip" data-t-title="bp_lbl" title="Approach signal" hidden>' in PAGE
    assert "t('bp_chip',r.d<1?'<1':Math.round(r.d),Math.max(0,Math.round(agoMin(r.m.pos_ts||r.m.ts))))" in PAGE
    assert "body.setup #fmchip,body.setup .jarbtn" in PAGE and "body.setup #beepchip" in PAGE
