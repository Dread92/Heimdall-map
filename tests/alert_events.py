"""1.58.4: the alert history is read from the start / end events, as the server writes them (State.alert_rows) — the
alerts table keeps one row per region and type, with the region's first start. Tests that store their alerts as rows
write the events of those rows here; an alert still on is in State.active, as the live sources keep it."""


def events_from_table(st, active=()):
    with st.store.lock:
        rows = st.store.conn.execute("SELECT key, location_uid, location_title, location_type, oblast_uid, alert_type, alert_level, "
                                     "started_at, finished_at, source FROM alerts").fetchall()
    for key, uid, title, lt, obl, at, lv, sa, fa, src in rows:
        ev = {"key": key, "location_uid": uid, "location_title": title, "alert_type": at, "oblast_uid": obl}
        st.store.add_event(dict(ev, ts=sa, kind="start"))
        if fa:
            st.store.add_event(dict(ev, ts=fa, kind="end"))
        elif key in active:
            st.active[key] = dict(ev, source=src, location_type=lt, alert_level=lv, started_at=sa, finished_at=None,
                                  location_title_en=None, notes=None, threats=[])
