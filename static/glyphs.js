// Heimdall — the weapon silhouettes, shared by the Tactical page (kyiv.html) and the Light page (light.html).
// One file so the two pages can never draw the same weapon two different ways.
// Each shape is drawn nose-up, centred on 0,0, about 24 units tall; a page scales and rotates it (only to a
// course the post reported — see orientOf() in kyiv.html and markOrient() in light.html).

// ONE SILHOUETTE PER WEAPON. (It turns only to a course the post reported — the history of that rule is below.)
// A symbol that rotates has to point somewhere, so a target reported without a course forced a choice
// between inventing a heading and drawing a second, different icon for the same weapon — which is how a
// Banderol ended up as an arrow in one place and a diamond in another. Air-defence displays settled this
// long ago: the symbol says WHAT it is, the leader line says where it is going. Here the symbol is fixed
// (every marker on the map sits at the same angle, so its nose cannot be read as a course) and the whole
// direction story lives in the chevron, the ray and the uncertainty cone — which appear only when a post
// actually gave a course, and are simply absent when it did not.
// The Shahed-136 as it actually looks from above: nose cone, slim fuselage, a big delta, fins at the wingtips
// and the engine at the tail. Drawn as shapes rather than a bitmap because the glyph has to take a colour —
// orange for a Shahed, amber for the jet, white in blackout mode, and the app tints it for other states too —
// and stay sharp at every zoom, neither of which a sprite sheet does. The sub-shapes overlap on purpose: the
// outline they share reads as panel lines at marker size.
const SHAHED_BODY='<path class="glyph" d="M0-11.6 L2-6.8 L2 6.2 L-2 6.2 L-2-6.8 Z"/>'
  +'<path class="glyph" d="M-2-3.6 L-10.4 6.2 L-2 6.2 Z"/><path class="glyph" d="M2-3.6 L10.4 6.2 L2 6.2 Z"/>'
  +'<rect class="glyph" x="-10.9" y="5.2" width="2.4" height="4.8" rx="0.5"/>'
  +'<rect class="glyph" x="8.5" y="5.2" width="2.4" height="4.8" rx="0.5"/>';
const G={drone:SHAHED_BODY+'<rect class="glyph" x="-2.8" y="6" width="5.6" height="4.4" rx="0.8"/>'
    +'<g class="jetfx"><path class="flame" d="M-2.4 10.4 L0 16.6 L2.4 10.4 Z"/><path class="flame2" d="M-1.1 10.4 L0 13.8 L1.1 10.4 Z"/></g>',
  // Same airframe, because it is the same airframe. What tells them apart is the turbojet: an intake on the
  // spine and a fatter nozzle — plus the flame, which only a jet one is drawn with.
  jetdrone:SHAHED_BODY+'<rect class="glyph" x="-3.3" y="-6.6" width="6.6" height="4.4" rx="2.2"/>'
    +'<rect class="glyph" x="-3.2" y="6" width="6.4" height="4.6" rx="0.8"/>'
    +'<g class="jetfx"><path class="flame" d="M-3 10.6 L0 19.5 L3 10.6 Z"/><path class="flame2" d="M-1.5 10.6 L0 15.6 L1.5 10.6 Z"/></g>',
  // swept wings: a cruise missile at a glance, and not the same shape as anything else here
  missile:'<path class="glyph" d="M0 -12 L1.3 -9 L1.3 9 L-1.3 9 L-1.3 -9 Z"/><path class="glyph" d="M1.3 -0.6 L5.4 1.8 L5.4 2.8 L1.3 1.9 Z"/><path class="glyph" d="M-1.3 -0.6 L-5.4 1.8 L-5.4 2.8 L-1.3 1.9 Z"/><path class="glyph" d="M1.3 6 L3.5 10.2 L1.3 9 Z"/><path class="glyph" d="M-1.3 6 L-3.5 10.2 L-1.3 9 Z"/>',
  // the S8000 as it is from above (1.58.34, the owner: "the icon is really ugly" — it was a cross of two bars): a slim
  // tapered body, straight wings set mid-body and swept back a touch, the small turbojet on its back behind the wing
  // (the fatter block that tells it from the Kalibr-class shape above), and an X-tail read as two fins. Nose up.
  banderol:'<path class="glyph" d="M0-11.6 L1.7-7.4 L1.7 8.2 L-1.7 8.2 L-1.7-7.4 Z"/><path class="glyph" d="M-1.7-1.2 L-10.6 1.4 L-10.6 2.9 L-1.7 2.2 Z"/><path class="glyph" d="M1.7-1.2 L10.6 1.4 L10.6 2.9 L1.7 2.2 Z"/><rect class="glyph" x="-2.9" y="1.6" width="5.8" height="5.6" rx="1.4"/><path class="glyph" d="M-1.7 6.2 L-5.8 10.4 L-5.8 11.6 L-1.7 9.4 Z"/><path class="glyph" d="M1.7 6.2 L5.8 10.4 L5.8 11.6 L1.7 9.4 Z"/><g class="jetfx"><path class="flame" d="M-1.6 8.4 L0 13.4 L1.6 8.4 Z"/><path class="flame2" d="M-0.8 8.4 L0 11.2 L0.8 8.4 Z"/></g>',
  ballistic:'<path class="glyph" d="M0 -12 L1.6 -7.6 L2.1 -4 L2.1 8 L-2.1 8 L-2.1 -4 L-1.6 -7.6 Z"/><path class="glyph" d="M2.1 4.2 L4.6 9.6 L2.1 8 Z"/><path class="glyph" d="M-2.1 4.2 L-4.6 9.6 L-2.1 8 Z"/><rect class="glyph" x="-1.3" y="8" width="2.6" height="1.8" rx="0.4"/>',
  bomb:'<path class="glyph" d="M0-10.5 C 3.6-6.5 4.4-1.5 4.4 3 L4.4 7 L-4.4 7 L-4.4 3 C -4.4-1.5 -3.6-6.5 0-10.5 Z"/>'
    +'<path class="glyph" d="M-4.4 4 L-8.2 11 L-4.4 9.6 Z"/><path class="glyph" d="M4.4 4 L8.2 11 L4.4 9.6 Z"/>'
    +'<path class="glyph" d="M-1.6 6.4 L1.6 6.4 L1.6 11.4 L-1.6 11.4 Z"/>',
  unknown:'<path class="glyph tri" d="M0-9 L9 7 L-9 7 Z"/><path d="M0-4 L0 1" stroke="#080b10" stroke-width="2" stroke-linecap="round"/><circle cx="0" cy="4" r="1.2" fill="#080b10"/>',
  down:'<path class="glyph x" d="M-7-7 L7 7 M7-7 L-7 7"/><circle class="glyph ring" cx="0" cy="0" r="9"/>',
  impact:'<path class="glyph x" d="M0-10 L2-3 L9-6 L4 0 L10 4 L3 3 L2 10 L-1 4 L-8 7 L-4 0 L-10-3 L-3-2 Z"/>',
  lost:'<circle class="glyph ring" cx="0" cy="0" r="8"/><text class="glyph q" x="0" y="3.5" text-anchor="middle">?</text>',
  clear:'<circle class="glyph ring" cx="0" cy="0" r="8"/><path class="glyph x" d="M-4 0 L-1 3 L5-4"/>'};
// Three shapes that were being drawn as something else. A Tu-95 heading for its launch line and a Kh-22
// already in flight are not the same warning, and until now they were the same picture. All of these are
// drawn nose-up in their own right, because the mark turns to the reported course.
//
// Aircraft, not missiles: a swept wing and a tail, so at a glance the silhouette says "something is flying
// that will launch" rather than "something is already on its way".
// Night mode's stand-in for every silhouette: one chevron, nose on the centreline like all the others, so
// it obeys the same rotation rule and points only where the post said.
G.arrow='<path class="glyph" d="M0-10 L7.2 8 L0 3.6 L-7.2 8 Z"/>';
G.supersonic='<path class="glyph" d="M0-12.5 L2.6-5 L2.6 1 L8.4 7 L8.4 9 L2.6 6.4 L2.6 9.2 L4.4 12 L-4.4 12 L-2.6 9.2 L-2.6 6.4 L-8.4 9 L-8.4 7 L-2.6 1 L-2.6-5 Z"/>'
  +'<path class="glyph" d="M0-12.5 L1.3-8 L-1.3-8 Z" opacity=".55"/>';
G.bomber='<path class="glyph" d="M0-12 L1.9-7.2 L1.9-1.2 L12.4 4.4 L12.4 6.6 L1.9 3.4 L1.9 7.6 L5.2 11.4 L5.2 12.6 L-5.2 12.6 L-5.2 11.4 L-1.9 7.6 L-1.9 3.4 L-12.4 6.6 L-12.4 4.4 L-1.9-1.2 L-1.9-7.2 Z"/>';
G.fighter='<path class="glyph" d="M0-12.8 L1.5-8.4 L1.5-2.6 L9.6 4.2 L9.6 6 L1.5 2.6 L1.5 7.4 L4.2 11.6 L4.2 12.8 L-4.2 12.8 L-4.2 11.6 L-1.5 7.4 L-1.5 2.6 L-9.6 6 L-9.6 4.2 L-1.5-2.6 L-1.5-8.4 Z"/>'
  +'<rect class="glyph" x="-5.4" y="8.2" width="1.5" height="4.2" rx="0.4"/><rect class="glyph" x="3.9" y="8.2" width="1.5" height="4.2" rx="0.4"/>';

// 1.58.42, the owner, of a ballistic missile "в напрямку Києва" drawn nose-up on Kyiv: "how to rotate the missile like a
// direction it takes usually?" — picked: no direction drawn at all. Upright is not a direction for a drone among drones,
// but a lone missile's nose reads as "heading north". So a missile, a Banderol or a guided bomb whose post gave no course
// — and that has no track of its own to face along (`face`) — is a disc with a "?", in its weapon's colour; the label
// still says what it is. It takes its silhouette, turned, as soon as a post gives a course.
const NOFRONT=new Set(['ballistic','missile','supersonic','banderol','bomb']);
const noFront=(gk,m,stated)=>NOFRONT.has(gk)&&!m.status&&!m.endedBy&&!stated&&m.face==null;
G.nofront='<circle class="glyph nf" cx="0" cy="0" r="8.4"/><text class="nfq" x="0" y="4.6" text-anchor="middle">?</text>';

// one weapon, one symbol — and the same symbol whether or not a course was reported
// One picture per weapon. A type that falls through to a neighbour's shape is a type the reader cannot tell
// apart from it — which is the whole job of a silhouette.
const GLYPH_BY_TYPE={drones:'drone',unknown:'unknown',banderol_missiles:'banderol',
  ballistic_missiles:'ballistic',supersonic_missiles:'supersonic',
  guided_aerial_bombs:'bomb',
  // The aircraft: still carrying, not yet launched. A different warning from the thing it will release.
  tactic_aircraft_activity:'fighter',strategic_aircraft_activity:'bomber',mig31k_departure:'fighter',
  cruise_missiles:'missile',unspecified_missiles:'missile'};
