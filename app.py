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
    phyto     = st.number_input("Physio. Gründigkeit (cm)", 10, 500, 100)
    bodenform = st.text_input("Bodenform")
    st.markdown("---")
    run       = st.button("Auswerten")

st.title("🌿 Bohrstock-Auswertung")

if run:
    st.write("Du hast eingegeben:")
    st.write(f"- Bohrstock Nr.: {bohrnr}")
    st.write(f"- Rechtswert:     {rechts}")
    st.write(f"- Hochwert:       {hoch}")

# — 1) Warte auf Datei —
if not uploaded:
    st.info("Bitte lade eine Datei in der Sidebar hoch.")
    st.stop()

# — 2) Datei einlesen mit Fehler-Handling —
try:
    if uploaded.name.lower().endswith(("xls","xlsx")):
        df = pd.read_excel(uploaded)
    else:
        df = pd.read_csv(uploaded)
except Exception as e:
    st.error(f"❌ Fehler beim Einlesen der Datei: {e}")
    st.stop()

if run:
    # — 3) Horizonte aufbereiten —
    try:
        horizonte = build_horizonte_list(df)
    except KeyError as e:
        st.error(f"❌ Spalte nicht gefunden: {e} – bitte Eingabedatei prüfen.")
        st.stop()
    except Exception as e:
        st.error(f"❌ Fehler bei Verarbeitung der Horizonte: {e}")
        st.stop()

    # — 4) Tabs anlegen —
    tab1, tab2, tab3 = st.tabs(["Rohdaten","Horizonte","Ergebnisse"])

    with tab1:
        st.subheader("📋 Eingelesene Rohdaten")
        st.dataframe(df, use_container_width=True)

    with tab2:
        st.subheader("🔍 Verarbeitete Horizonte")
        st.dataframe(pd.DataFrame(horizonte), use_container_width=True)

    # — 5) Oberboden-Werte extrahieren —
    try:
        ober = min(horizonte, key=lambda h: h["z_top"])
    except Exception as e:
        st.error(f"❌ Kein Oberboden-Horizont gefunden: {e}")
        st.stop()

    bodentyp = ober.get("Bodenart","").strip()
    if not bodentyp:
        st.error("❌ Bodenart im Oberboden fehlt.")
        st.stop()
    if bodentyp not in bodentyp_to_bg:
        zul = ", ".join(sorted(bodentyp_to_bg.keys()))
        st.error(f"❌ Ungültige Bodenart '{bodentyp}'. Zulässige Klassen: {zul}")
        st.stop()

    bg         = bodentyp_to_bg[bodentyp]
    ph_wert    = ober.get("pH")
    humus_wert = ober.get("humus")

    if pd.isna(ph_wert):
        st.warning("⚠️ pH-Wert im Oberboden fehlt; Kalkbedarf wird übersprungen.")
    if pd.isna(humus_wert):
        st.warning("⚠️ Humus-Wert im Oberboden fehlt; Kalkbedarf wird übersprungen.")

    # — 6) Kalkbedarf berechnen —
    try:
        df_acker = pd.read_csv("kalkbedarf_acker.csv")
        df_gruen = pd.read_csv("kalkbedarf_gruen.csv")
    except Exception as e:
        st.error(f"❌ Fehler beim Laden der Kalkbedarf-Tabellen: {e}")
        st.stop()

    kalk, msg = berechne_kalkbedarf(
        bg, ph_wert, humus_wert,
        nutzungsart=nutzung.lower(),
        df_acker=df_acker,
        df_gruen=df_gruen,
    )
    if msg:
        st.warning(f"⚠️ {msg}")
    kalk_value = f"{kalk:.1f}" if kalk is not None else "Kein Bedarf"

    # — 7) Kapillar-Aufstiegsrate —
    try:
        kap = kapillaraufstiegsrate(horizonte, phyto)
        kap_text = f"{kap:.2f}" if kap is not None else "N/A"
    except Exception as e:
        st.warning(f"⚠️ Fehler bei Kapillar-Aufstiegsrate: {e}")
        kap_text = "Fehler"

    # — 8) Humusvorrat und nFK —
    try:
        _, total_hum = humusvorrat(horizonte, max_tiefe=100)
        hum_text = f"{total_hum*10:.1f}"
    except Exception as e:
        st.error(f"❌ Fehler bei Humusvorrat: {e}")
        st.stop()
    try:
        nfk = gesamt_nfk(horizonte, phyto)
        nfk_text = f"{nfk:.0f}"
    except Exception as e:
        st.warning(f"⚠️ Fehler bei nFK-Berechnung: {e}")
        nfk_text = "Fehler"

    # — 9) Ergebnisse anzeigen —
    with tab3:
        st.subheader("✅ Zusammenfassung")
        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Humusvorrat 1 m (Mg/ha)", hum_text)
        c2.metric("pH Oberboden",           f"{ph_wert:.2f}" if ph_wert is not None else "N/A")
        c3.metric("nFK (mm)",               nfk_text)
        c4.metric("Kalkbedarf (dt CaO/ha)", kalk_value)
        c5.metric("Kapillar-Aufstiegsrate (mm/d)", kap_text)

        st.markdown("---")
        # Metadaten und Kennzahlen in der Tabelle
        result_df = pd.DataFrame([{
            "Bohrstock-Nr.":                    bohrnr,
            "Rechtswert":                       rechts,
            "Hochwert":                         hoch,
            "Bodentyp":                         bodentyp,
            "Bodenform":                        bodenform,
            "Physio. Gründigkeit (cm)":         phyto,
            "Humusvorrat bis 1 m (Mg/ha)":      total_hum*10,
            "pH Oberboden":                     ph_wert,
            "Kalkbedarf (dt CaO/ha)":           kalk_value,
            "nFK (mm)":                         nfk_text,
            "Kapillar-Aufstiegsrate (mm/d)":    kap_text
        }])
        st.dataframe(result_df, use_container_width=True)

        # — 10) Download —
        buffer = io.BytesIO()
        try:
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                result_df.to_excel(writer, index=False)
            buffer.seek(0)
            st.download_button(
                "Ergebnis als Excel herunterladen",
                data=buffer,
                file_name="ergebnis.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as e:
            st.error(f"❌ Fehler beim Erzeugen der Excel-Datei: {e}")
