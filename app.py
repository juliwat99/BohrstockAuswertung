import streamlit as st
import pandas as pd
import io

from bodenauswertung import (
    humusvorrat,
    berechne_kalkbedarf,
    gesamt_nfk,
    bodentyp_to_bg,
    build_horizonte_list,
    humuskategorie,
    kapillaraufstiegsrate,
    # Für Rechenweg
    zone_von_bd,
    get_org_factor,
    df_full,
    _KAP_TABLE,
    _KAP_DMS
)

# — Seite konfigurieren —
st.set_page_config(
    page_title="Bohrstock-Auswertung",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
)

# — Sidebar für Inputs —
with st.sidebar:
    st.header("Einstellungen")
    bohrnr    = st.text_input("Bohrstock-Nr.")
    rechts    = st.text_input("Rechtswert")
    hoch      = st.text_input("Hochwert")
    uploaded  = st.file_uploader("Excel/CSV hochladen", type=["xlsx","csv"])
    nutzung   = st.selectbox("Nutzungsart", ["Acker","Gruenland"])
    phyto     = st.number_input("Physio. Gründigkeit (cm)", min_value=10, max_value=500, value=100)
    bodenform = st.text_input("Bodenform")
    st.markdown("---")
    run       = st.button("Auswerten")

st.title("🌿 Bohrstock-Auswertung")

# 1) Meta-Werte anzeigen
if run:
    st.markdown("**Eingegebene Metadaten**")
    st.write(f"- **Bohrnr.**: {bohrnr or '–'}")
    st.write(f"- **Rechtswert**: {rechts or '–'}")
    st.write(f"- **Hochwert**: {hoch or '–'}")

# 2) Auf Datei warten
if not uploaded:
    st.info("Bitte lade eine Datei in der Sidebar hoch.")
    st.stop()

# 3) Datei einlesen
try:
    if uploaded.name.lower().endswith(("xls","xlsx")):
        df = pd.read_excel(uploaded)
    else:
        df = pd.read_csv(uploaded, sep=None, engine="python")
except Exception as e:
    st.error(f"❌ Fehler beim Einlesen der Datei: {e}")
    st.stop()

# 3.1) Tiefenangaben mit “+” normalisieren
depth_col = [c for c in df.columns if "tiefe" in c.lower()][0]
df[depth_col] = (
    df[depth_col]
      .astype(str)
      .str.replace(r"(\d+)\+", r"\1-", regex=True)
)
if run:
    # 4) Horizonte verarbeiten
    try:
        horizonte = build_horizonte_list(df)
    except KeyError as e:
        st.error(f"❌ Spalte nicht gefunden: {e} → bitte Eingabedatei prüfen.")
        st.stop()
    except Exception as e:
        st.error(f"❌ Fehler bei Verarbeitung der Horizonte: {e}")
        st.stop()

    # 5) Tabs aufbauen
    tab1, tab2, tab3, tab4 = st.tabs([
        "Rohdaten", "Horizonte", "Rechenweg", "Ergebnisse"
    ])

    # — Tab 1: Rohdaten —
    with tab1:
        st.subheader("📋 Eingelesene Rohdaten")
        st.dataframe(df, use_container_width=True)

    # — Tab 2: Verarbeitete Horizonte —
    with tab2:
        st.subheader("🔍 Verarbeitete Horizonte")
        st.dataframe(pd.DataFrame(horizonte), use_container_width=True)

    # 6) Oberboden extrahieren & Grundwerte
    try:
        ober = min(horizonte, key=lambda h: h["z_top"])
    except Exception as e:
        st.error(f"❌ Kein Oberboden-Horizont gefunden: {e}")
        st.stop()

    bodentyp = (ober.get("Bodenart") or "").strip()
    if not bodentyp:
        st.error("❌ Bodenart im Oberboden fehlt.")
        st.stop()
    if bodentyp not in bodentyp_to_bg:
        zul = ", ".join(sorted(bodentyp_to_bg.keys()))
        st.error(f"❌ Ungültige Bodenart «{bodentyp}». Zulässig: {zul}")
        st.stop()
    bg = bodentyp_to_bg[bodentyp]

    ph_wert    = ober.get("pH")
    humus_wert = ober.get("humus")
    if pd.isna(ph_wert):
        st.warning("⚠️ pH im Oberboden fehlt → Kalkbedarf übersprungen.")
    if pd.isna(humus_wert):
        st.warning("⚠️ Humus im Oberboden fehlt → Kalkbedarf übersprungen.")

    # 7) Kalkbedarf
    try:
        df_acker = pd.read_csv("kalkbedarf_acker.csv")
        df_gruen = pd.read_csv("kalkbedarf_gruen.csv")
    except Exception as e:
        st.error(f"❌ Kalkbedarf-Tabellen nicht gefunden: {e}")
        st.stop()
    kalk, msg = berechne_kalkbedarf(
        bg, ph_wert, humus_wert,
        nutzungsart=nutzung.lower(),
        df_acker=df_acker, df_gruen=df_gruen
    )
    if msg:
        if "Kein pH-Wert" in msg:
            st.warning(f"⚠️ {msg}")
            kalk_value = ""
        else:
            st.warning(f"⚠️ {msg}")
            kalk_value = "Kein Bedarf"
    else:
        kalk_value = f"{kalk:.1f}"

    # 8) Kapillar-Aufstiegsrate
    try:
        kap = kapillaraufstiegsrate(horizonte, phyto)
        kap_text = f"{kap:.2f}" if kap is not None else "N/A"
    except Exception as e:
        st.warning(f"⚠️ Kapillar-Aufstiegsrate: {e}")
        kap_text = "Fehler"

    # 9) Humusvorrat & nFK
    try:
        df_humus, total_hum = humusvorrat(horizonte, max_tiefe=100)
        hum_text = f"{total_hum*10:.1f}"
    except Exception as e:
        st.error(f"❌ Humusvorrat-Fehler: {e}")
        st.stop()
    try:
        nfk = gesamt_nfk(horizonte, phyto)
        nfk_text = f"{nfk:.0f}"
    except Exception as e:
        st.warning(f"⚠️ nFK-Fehler: {e}")
        nfk_text = "Fehler"

    # — Tab 3: Rechenweg Humus, nFK & Kapillar-Aufstieg —
    with tab3:
        st.subheader("🧮 Rechenweg")

        # 1) Humusvorrat
        st.markdown("**Humusvorrat bis 100 cm**")
        st.dataframe(
            df_humus[[
                "hz","z_top","z_bot","z_bot_filled","eff_z_bot","eff_dicke_cm",
                "bd","humus","humus_g_cm2","humus_kg_m2"
            ]],
            use_container_width=True
        )
        st.write(f"→ Summe humus_kg_m2 × 10 = **{total_hum*10:.1f} Mg/ha**")

        # 2) nFK
        st.markdown("**nFK-Berechnung bis physiogr. Tiefe**")
        rows = []
        for h in horizonte:
            z_bot_f = h["z_bot"] if h["z_bot"] is not None else phyto
            eff_bot = min(z_bot_f, phyto)
            eff_d   = max(eff_bot - h["z_top"], 0)
            zone    = zone_von_bd(h["bd"])
            base_fk = df_full.at[h["Bodenart"], f"nutzbareFK_{zone}"]
            korr_h  = get_org_factor(h["Bodenart"], h["humus"])
            wert    = base_fk * korr_h * (1 - h["skelett"]/100)
            beitrag = wert * eff_d/100*10
            rows.append({
                "hz": h["hz"],
                "z_top": h["z_top"],
                "eff_dicke_cm": eff_d,
                "Zone": zone,
                "Basis FK [mm]": base_fk,
                "Humus-Faktor": f"{korr_h:.2f}",
                "Skelett-Abzug": f"{h['skelett']}%",
                "FK korr. [mm]": f"{wert:.2f}",
                "Beitrag [mm]": f"{beitrag:.1f}"
            })
        df_nfk = pd.DataFrame(rows)
        st.dataframe(df_nfk, use_container_width=True)
        st.write(f"→ Summe Beitrag = **{nfk:.0f} mm**")

         # 3) Kapillar-Aufstiegsrate
        st.markdown("**Kapillar-Aufstiegsrate**")
        gr_h = next(
            (h for h in horizonte if isinstance(h.get("hz"), str) and "gr" in h["hz"].lower()),
            None
        )
        if not gr_h:
            st.write("→ Kein Gr-Horizont gefunden → Rate = 0 mm/d")
        else:
            start_cm = gr_h["z_top"]
            dist_cm  = start_cm - phyto
        
            # **Neu**: wenn der Abstand ≤ 0, keine Aufstiegsmächtigkeit → 0 mm/d
            if dist_cm <= 0:
                st.write(f"- Gr-Horizont **{gr_h['hz']}**, z_top = {start_cm} cm")
                st.write(f"- physiologische Tiefe = {phyto} cm → Abstand = {dist_cm} cm ≤ 0 → Rate = 0 mm/d")
            else:
                dist_dm  = dist_cm / 10
                dm_sel   = min(_KAP_DMS, key=lambda x: abs(x - dist_dm))
        
                st.write(f"- Gr-Horizont **{gr_h['hz']}**, z_top = {start_cm} cm")
                st.write(f"- physiologische Tiefe = {phyto} cm → Abstand = {dist_cm} cm = {dist_dm:.1f} dm → Spalte = {dm_sel} dm")
                st.write(f"- Bodenart im Gr-Horizont: {gr_h['Bodenart']}")
        
                val = _KAP_TABLE.loc[
                    _KAP_TABLE["Bodenart"]
                        .str.lower()
                        .str.contains(gr_h["Bodenart"].split()[0].lower(), na=False),
                    str(dm_sel)
                ].iat[0]
        
                if isinstance(val, str) and val.strip().startswith(">"):
                    st.write(f"- Tabellen-Wert = `{val}` → **> {val.strip()[1:]} mm/d**")
                else:
                    try:
                        rate = float(str(val).replace(",", "."))
                        st.write(f"- Tabellen-Wert = `{val}` → **{rate:.2f} mm/d**")
                    except:
                        st.write(f"- Tabellen-Wert = `{val}` → **k.A.**")





    # — Tab 4: Endergebnisse —
    with tab4:
        st.subheader("✅ Zusammenfassung")
        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Humusvorrat 1 m (Mg/ha)",    hum_text)
        c2.metric("pH Oberboden",              f"{ph_wert:.2f}" if pd.notna(ph_wert) else "N/A")
        c3.metric("nFK (mm)",                  nfk_text)
        c4.metric("Kalkbedarf (dt CaO/ha)",    kalk_value or "–")
        c5.metric("Kapillar-Rate (mm/d)",      kap_text)

        st.markdown("---")
        result_df = pd.DataFrame([{
            "Bohrstock-Nr.":                bohrnr,
            "Rechtswert":                   rechts,
            "Hochwert":                     hoch,
            "Bodentyp":                     bodentyp,
            "Bodenform":                    bodenform,
            "Phys. Gründigkeit (cm)":       phyto,
            "Humusvorrat bis 1 m (Mg/ha)":  total_hum*10,
            "pH Oberboden":                 ph_wert,
            "Kalkbedarf (dt CaO/ha)":       kalk_value,
            "nFK (mm)":                     nfk_text,
            "Kapillar-Rate (mm/d)":         kap_text
        }])
        st.dataframe(result_df, use_container_width=True)

        buf = io.BytesIO()
        try:
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                result_df.to_excel(w, index=False)
            buf.seek(0)
            st.download_button(
                "Ergebnis als Excel herunterladen",
                data=buf,
                file_name="ergebnis.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as e:
            st.error(f"❌ Export-Fehler: {e}")
