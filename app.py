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

# 1) Meta-Werte schon mal anzeigen
if run:
    st.markdown("**Eingegebene Metadaten**")
    st.write(f"- **Bohrnr.**: {bohrnr or '–'}")
    st.write(f"- **Rechtswert**: {rechts or '–'}")
    st.write(f"- **Hochwert**: {hoch or '–'}")

# 2) Auf Datei warten
if not uploaded:
    st.info("Bitte lade eine Datei in der Sidebar hoch.")
    st.stop()

# 3) Datei einlesen (Excel oder CSV, mit automatischem Separator-Detect)
try:
    if uploaded.name.lower().endswith(("xls","xlsx")):
        df = pd.read_excel(uploaded)
    else:
        df = pd.read_csv(uploaded, sep=None, engine="python")
except Exception as e:
    st.error(f"❌ Fehler beim Einlesen der Datei: {e}")
    st.stop()

if run:
    # 4) Horizonte bauen
    try:
        horizonte = build_horizonte_list(df)
    except KeyError as e:
        st.error(f"❌ Spalte nicht gefunden: {e} → bitte Eingabedatei prüfen.")
        st.stop()
    except Exception as e:
        st.error(f"❌ Fehler bei Verarbeitung der Horizonte: {e}")
        st.stop()

    # 5) Tabs aufbauen
    tab1, tab2, tab3 = st.tabs(["Rohdaten","Horizonte","Ergebnisse"])
    with tab1:
        st.subheader("📋 Eingelesene Rohdaten")
        st.dataframe(df, use_container_width=True)
    with tab2:
        st.subheader("🔍 Verarbeitete Horizonte")
        st.dataframe(pd.DataFrame(horizonte), use_container_width=True)

    # 6) Oberboden extrahieren
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
        st.error(f"❌ Ungültige Bodenart «{bodentyp}». Zulässig sind: {zul}")
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
        st.error(f"❌ Tabellen Kalkbedarf nicht gefunden: {e}")
        st.stop()

    kalk, msg = berechne_kalkbedarf(
        bg, ph_wert, humus_wert,
        nutzungsart=nutzung.lower(),
        df_acker=df_acker, df_gruen=df_gruen
    )
    if msg:
        # bei fehlendem pH nur warnen, Kalkzelle leer lassen
        if "Kein pH-Wert" in msg:
            st.warning(f"⚠️ {msg}")
            kalk_value = ""
        else:
            st.warning(f"⚠️ {msg}")
            kalk_value = "Kein Bedarf"
    else:
        kalk_value = f"{kalk:.1f}"

    # 8) Kapillaraufstiegsrate
    try:
        kap = kapillaraufstiegsrate(horizonte, phyto)
        kap_text = f"{kap:.2f}" if kap is not None else "N/A"
    except Exception as e:
        st.warning(f"⚠️ Kapillar-Aufstiegsrate: {e}")
        kap_text = "Fehler"

    # 9) Humusvorrat & nFK
    try:
        _, total_hum = humusvorrat(horizonte, max_tiefe=100)
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

    # 10) Ergebnisse‐Tab
    with tab3:
        st.subheader("✅ Zusammenfassung")
        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Humusvorrat 1 m (Mg/ha)",    hum_text)
        c2.metric("pH Oberboden",             f"{ph_wert:.2f}" if pd.notna(ph_wert) else "N/A")
        c3.metric("nFK (mm)",                  nfk_text)
        c4.metric("Kalkbedarf (dt CaO/ha)",    kalk_value or "–")
        c5.metric("Kap. Aufstiegsrate (mm/d)", kap_text)

        st.markdown("---")
        result_df = pd.DataFrame([{
            "Bohrstock-Nr.":                   bohrnr,
            "Rechtswert":                      rechts,
            "Hochwert":                        hoch,
            "Bodentyp":                        bodentyp,
            "Bodenform":                       bodenform,
            "Phys. Gründigkeit (cm)":          phyto,
            "Humusvorrat bis 1 m (Mg/ha)":     total_hum*10,
            "pH Oberboden":                    ph_wert,
            "Kalkbedarf (dt CaO/ha)":          kalk_value,
            "nFK (mm)":                        nfk_text,
            "Kapillar-Rate (mm/d)":            kap_text
        }])
        st.dataframe(result_df, use_container_width=True)

        # 11) Download
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
