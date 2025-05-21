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
    uploaded  = st.file_uploader("Excel/CSV hochladen", type=["xlsx","csv"])
    nutzung   = st.selectbox("Nutzungsart", ["Acker","Gruenland"])
    phyto     = st.number_input("Physio. Gründigkeit (cm)", min_value=10, max_value=500, value=100)
    bodenform = st.text_input("Bodenform")
    st.markdown("---")
    run = st.button("Auswerten")

st.title("🌿 Bohrstock-Auswertung")

# Warten auf Datei
if not uploaded:
    st.info("Bitte lade eine Datei in der Sidebar hoch.")
    st.stop()

# — Daten einlesen mit Fehlerabfang —
try:
    if uploaded.name.lower().endswith(("xls","xlsx")):
        df = pd.read_excel(uploaded)
    else:
        df = pd.read_csv(uploaded)
except Exception as e:
    st.error(f"❌ Fehler beim Einlesen der Datei: {e}")
    st.stop()

if run:
    # 1) Horizonte verarbeiten
    try:
        horizonte = build_horizonte_list(df)
    except KeyError as e:
        st.error(f"❌ Spalten nicht gefunden: {e}. Bitte überprüfe Deine Eingabedatei.")
        st.stop()
    except Exception as e:
        st.error(f"❌ Fehler beim Verarbeiten der Horizonte: {e}")
        st.stop()

    # 2) Tabs
    tab1, tab2, tab3 = st.tabs(["Rohdaten","Horizonte","Ergebnisse"])

    with tab1:
        st.subheader("📋 Eingelesene Rohdaten")
        st.dataframe(df, use_container_width=True)

    with tab2:
        st.subheader("🔍 Verarbeitete Horizonte")
        st.dataframe(pd.DataFrame(horizonte), use_container_width=True)

    # 3) Oberboden-Werte extrahieren
    try:
        ober = min(horizonte, key=lambda h: h["z_top"])
    except Exception as e:
        st.error(f"❌ Kein gültiger Oberboden-Horizont gefunden: {e}")
        st.stop()

    bodentyp = ober.get("Bodenart", "").strip()
    if not bodentyp:
        st.error("❌ Bodenart des Oberbodens fehlt.")
        st.stop()

    if bodentyp not in bodentyp_to_bg:
        gültige = ", ".join(sorted(bodentyp_to_bg.keys()))
        st.error(f"❌ Ungültige Bodenart „{bodentyp}“. Zulässige Klassen sind: {gültige}.")
        st.stop()

    bg = bodentyp_to_bg[bodentyp]
    ph_wert    = ober.get("pH")
    humus_wert = ober.get("humus")

    if pd.isna(ph_wert):
        st.warning("⚠️ pH-Wert im Oberboden fehlt; Kalkbedarf wird übersprungen.")
    if pd.isna(humus_wert):
        st.warning("⚠️ Humus-Wert im Oberboden fehlt; Kalkbedarf wird übersprungen.")

    # 4) Kalkbedarf berechnen
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

    # 5) Kapillar-Aufstiegsrate
    try:
        kap_rate = kapillaraufstiegsrate(horizonte, phyto)
        kap_text = f"{kap_rate:.2f}" if kap_rate is not None else "N/A"
    except Exception as e:
        st.warning(f"⚠️ Fehler bei Kapillar-Aufstiegsrate: {e}")
        kap_text = "Fehler"

    # 6) Humusvorrat und nFK
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

    # 7) Ausgabe im Ergebnis-Tab
    with tab3:
        st.subheader("✅ Zusammenfassung")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Humusvorrat 1 m (Mg/ha)", hum_text)
        c2.metric("pH Oberboden",            f"{ph_wert:.2f}" if ph_wert is not None else "N/A")
        c3.metric("nFK (mm)",                nfk_text)
        c4.metric("Kalkbedarf (dt CaO/ha)",  kalk_value)
        c5.metric("Kap. Aufstiegsrate (mm/d)", kap_text)

        st.markdown("---")
        result_df = pd.DataFrame([{
            "Bodentyp":                            bodentyp,
            "Bodenform":                           bodenform,
            "Physio. Gründigkeit (cm)":            phyto,
            "Humusvorrat bis 1 m (Mg/ha)":         total_hum * 10,
            "pH Oberboden":                        ph_wert,
            "Kalkbedarf (dt CaO/ha)":              kalk_value,
            "nFK (mm)":                            nfk_text,
            "Kapillar-Aufstiegsrate (mm/d)":       kap_text
        }])
        st.dataframe(result_df, use_container_width=True)

        # Download-Button
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
