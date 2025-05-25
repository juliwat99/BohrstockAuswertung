import pandas as pd
import re


# (1) Humusvorrat
def humusvorrat(horizonte, max_tiefe=100):
    """
    Berechnet den Humusvorrat bis max_tiefe (cm).
    Wenn der unterste Horizont weniger als max_tiefe abdeckt,
    wird sein unteres Ende künstlich auf max_tiefe gesetzt.
    """
    # 1) DataFrame aufbauen und nach z_top sortieren
    df = pd.DataFrame(horizonte).sort_values("z_top").reset_index(drop=True)

    # 2) z_bot_filled: NaNs auffüllen mit max_tiefe
    df["z_bot_filled"] = df["z_bot"].fillna(max_tiefe)

    # 3) Wenn der unterste Horizont nicht bis max_tiefe reicht, 
    #    setze sein z_bot_filled ebenfalls auf max_tiefe
    if df.loc[df.index[-1], "z_bot_filled"] < max_tiefe:
        df.loc[df.index[-1], "z_bot_filled"] = max_tiefe

    # 4) eff_z_bot: auf max_tiefe clippen (sicherheitshalber)
    df["eff_z_bot"] = df["z_bot_filled"].clip(upper=max_tiefe)

    # 5) effektive Dicke
    df["eff_dicke_cm"] = (df["eff_z_bot"] - df["z_top"]).clip(lower=0)

    # 6) Humusmasse pro cm² (g/cm²)
    df["humus_g_cm2"] = (df["humus"] / 100) * df["bd"] * df["eff_dicke_cm"]

    # 7) Umrechnung in kg/m²
    df["humus_kg_m2"] = df["humus_g_cm2"] * 10

    # 8) Summe über alle Horizonte mit eff_dicke_cm > 0
    total = df.loc[df["eff_dicke_cm"] > 0, "humus_kg_m2"].sum()

    return df, total


# (2) Bodenart → Bodenartengruppe
bodentyp_to_bg = {
    "S":1, "Su2":1, "Ss":1,
    "Su3":2,"Su4":2, "Sl2":2,"l'S":2, "Sl3":2, "St2":2,
    "Sl4":3, "Slu":3, "lS":3, "St3":3, 
    "sL":4, "uL":4, "Lu":4, "Ls2":4,"Ls3":4,"Ls4":4,"Ts4":4,"UU":4, "Us":4,"Uls":4,"Ut2":4,"Ut3":4,"Ut4":4,
    "t'L":5, "tL":5, "lT":5, "T":5,"Lt2":5,"Lt3":5,"Lts":5,"Ts3":5,"Ts2":5,"Tl":5,"Tu2":5,"Tu3":5,"Tu4":5,"Tt":5,
    "Mo":6
}

def humuskategorie(humus, nutzungsart="acker"):
    """
    Gibt die Humuskategorie zurück, abhängig von der Nutzungsart.
    Für Acker:     <4, 4.1-8.0, 8.1-15.0, 15.1-30.0, >30.0
    Für Grünland:  ≤15.0, 15.1-30.0, >30.0
    """
    if nutzungsart.lower() in ("gruenland", "grünland"):
        if humus <= 15.0:
            return "≤15.0"
        if humus <= 30.0:
            return "15.1-30.0"
        return ">30.0"
    else:
        # Acker-Einteilung
        if humus < 4.1:
            return "<4"
        if humus <= 8.0:
            return "4.1-8.0"
        if humus <= 15.0:
            return "8.1-15.0"
        if humus <= 30.0:
            return "15.1-30.0"
        return ">30.0"



def ph_klasse_bestimmen(bg, kat, pH):
    for lo, hi, cls in ph_klassengrenzen[bg][kat]:
        if (lo is None or pH >= lo) and (hi is None or pH <= hi):
            return cls
    return None


def berechne_kalkbedarf(bg, pH, humus, nutzungsart, df_acker, df_gruen):
    """
    bg: Bodenartgruppe (1–6)
    pH: numerischer pH-Wert oder NaN
    humus: numerischer Humus-Anteil
    nutzungsart: "acker" oder "gruen"
    df_acker, df_gruen: die DataFrames aus den CSVs
    """
    if pd.isna(pH):
        return None, "Kein pH-Wert im Oberboden angegeben."

    df = df_acker if nutzungsart == "acker" else df_gruen

    # Humuskategorie jetzt mit Nutzungsart
    kat = humuskategorie(humus, nutzungsart)

    mask = (
        (df.bg == bg) &
        (df.humus_kat == kat) &
        ((df.pH_lo.isna()) | (df.pH_lo <= pH)) &
        ((df.pH_hi.isna()) | (pH <= df.pH_hi))
    )
    sub = df.loc[mask, "CaO"]
    if sub.empty:
        return None, f"Kein Kalkbedarf für bg={bg}, Humus={kat}, pH={pH} gefunden."
    return float(sub.iloc[0]), None


# (6) nFK
data_full = {
    "Bodenart": ["Ss", "Sl2", "Sl3", "Sl4", "Slu", "St2", "St3", "Su2", "Su3", "Su4", "Ls2", "Ls3", "Ls4", "Lt2", "Lt3", "Lts", "Lu", "Uu", "Uls", "Us", "Ut2", "Ut3", "Ut4", "Tt", "Tl", "Tu2", "Tu3", "Tu4", "Ts2", "Ts3", "Ts4", "fS", "fSms", "fSgs", "mS", "mSfs", "mSgs", "gS"],
    "nutzbareFK_pt1+2": [9,20,22,22,23,18,18,20,25,27,21,21,20,18,17,17,21,30,24,28,28,26,23,15,15,16,17,19,16,16,17,10,10,10,9,9,9,8],
    "nutzbareFK_pt3":   [7,18,18,18,21,16,15,18,21,23,16,16,16,14,12,14,17,26,22,25,26,25,21,13,13,12,13,17,13,13,14,9,9,9,6,6,6,5],
    "nutzbareFK_pt4+5": [7,17,17,15,19,13,12,17,20,21,14,14,13,11,10,11,15,23,21,22,23,23,19,12,11,10,10,16,12,11,11,8,8,8,5,5,5,4]
}
df_full = pd.DataFrame(data_full).set_index("Bodenart")

org_korrektur = {
    "Sand":  {(1,2):2, (2,4):4, (4,8):5, (8,15):6},
    "LUT":   {(1,2):1, (2,4):2, (4,8):4, (8,15):8}
}

def get_org_factor(bodenart, humus):
    """
    Gibt den Humuskorrekturfaktor (Multiplikator) zurück.
    """
    if humus <= 1:
        return 1.0
    key = "Sand" if bodenart.startswith("S") else "LUT"
    for (low, high), perc in org_korrektur[key].items():
        if low <= humus < high:
            return 1 + perc / 100
    return 1.0

def nfk_horizont(bodenart, skelett, humus, zone):
    """
    Berechnet die nutzbare Feldkapazität für einen Horizont.
    """
    base = df_full.at[bodenart, f"nutzbareFK_{zone}"]
    # Humuskorrektur
    base *= get_org_factor(bodenart, humus)
    # Abzug Skelettanteil
    return base * (1 - skelett / 100)

def zone_von_bd(bd):
    if bd < 1.4:
        return "pt1+2"
    elif bd < 1.6:
        return "pt3"
    else:
        return "pt4+5"

def gesamt_nfk(horizonte, phyto_tiefe=100):
    df = pd.DataFrame(horizonte).sort_values("z_top")

    # Wenn z_bot fehlt, so tun, als ginge der Horizont bis mindestens physiogr
    df["z_bot_filled"] = df["z_bot"].fillna(phyto_tiefe)

    # Effektiver Untergrund bis physiologischen Grenzwert
    df["eff_z_bot"]    = df["z_bot_filled"].clip(upper=phyto_tiefe)
    df["eff_dicke_cm"] = df["eff_z_bot"] - df["z_top"]

    # Nur echte Dicken > 0 behalten (NaN und ≤0 fliegen raus)
    df = df[df["eff_dicke_cm"] > 0].copy()

    total_mm = 0.0
    for _, row in df.iterrows():
        zone = zone_von_bd(row["bd"])
        wert = nfk_horizont(
            row["Bodenart"],
            row.get("skelett", 0),
            row["humus"],
            zone
        )
        # wert [mm pro 100 cm] → mm für eff_dicke_cm
        total_mm += wert * row["eff_dicke_cm"] / 100 * 10

    return total_mm

import pandas as pd
import re

def build_horizonte_list(df):
    cols = df.columns.tolist()
    def find_col(*keys):
        for c in cols:
            if all(k.lower() in c.lower() for k in keys):
                return c
        raise KeyError(f"Keine Spalte mit {keys!r} gefunden.")

    col_tiefe    = find_col("tiefe")
    col_bd       = find_col("trocken", "dichte")
    col_skelett  = find_col("skelett")
    col_humus    = find_col("humus")
    col_ph       = find_col("ph")
    col_bodenart = find_col("bodenart")
    col_horizont = find_col("horizont")

    df = df.copy()

   depth = df[col_tiefe].astype(str).str.strip()
    depth = (
    depth
    .str.replace("–", "-", regex=False)
    .str.replace("—", "-", regex=False)
    .str.replace(r"(\d+)\+", r"\1-", regex=True)  # "70+" → "70-"
    	)
splits = depth.str.split("-", expand=True)
df["z_top"] = pd.to_numeric(splits[0], errors="coerce")
df["z_bot"] = pd.to_numeric(splits[1], errors="coerce")

    # — Parser für Zahlen, Ranges und Prozentangaben —
    def parse_number_or_range(val):
        s = str(val).strip()
        # normalize dashes, comma→dot, strip percent
        s = s.replace("–", "-").replace("—", "-").replace(",", ".").replace("%", "")
        # "<X" → X/2
        m = re.match(r"<\s*(\d+(\.\d+)?)$", s)
        if m:
            return float(m.group(1)) / 2
        # "X-Y" → Mittelwert
        if "-" in s:
            lo, hi = s.split("-", 1)
            try:
                return (float(lo) + float(hi)) / 2
            except:
                pass
        # einzelner Wert
        try:
            return float(s)
        except:
            return None

    # — Dichte (bd) —
    df[col_bd] = df[col_bd].apply(parse_number_or_range)

    # — Skelett (%) —> Null ersetzt, falls leer oder unparsebar
    df[col_skelett] = df[col_skelett].apply(lambda v: parse_number_or_range(v) or 0.0)

    # — pH — mit demselben Parser für Ranges, aber hier einfacher:
    df[col_ph] = df[col_ph].apply(lambda v: parse_number_or_range(v))

    # — Humus —
    df["humus_num"] = df[col_humus].apply(parse_number_or_range)

    # — Liste bauen —
    horizonte = []
    for _, row in df.iterrows():
        horizonte.append({
            "hz":       row[col_horizont],
            "z_top":    row["z_top"],
            "z_bot":    row["z_bot"],
            "bd":       row[col_bd],
            "humus":    row["humus_num"],
            "pH":       row[col_ph],
            "Bodenart": row[col_bodenart],
            "skelett":  row[col_skelett]
        })
    return horizonte




_KAP_TABLE = pd.DataFrame([
    ["X",           "",   "",    "",   "",   "",    "",    "",    "",    "",    "",    ""],
    ["Sl2, Sl3, Sl4", ">5", ">5", "3", "1,5","1", "0,4",  "0,2",  "0,1",  "",     "",    ""],
    ["Su",          ">5", "5",   "3", "2",  "1,2","0,6",  "0,2",  "0,1",  "",     "",    ""],
    ["Ls2, Ls3, Ls4",">5", ">5", "2,3","1,4","1,1","0,5",  "0,3",  "0,1",  "",     "",    ""],
    ["Lu",          ">5", ">5", ">5", "5",  "3",  "1,5",  "0,8",  "0,4",  "0,2",  "",    ""],
    ["Ut2, Ut3, Ut4",">5",">5", ">5", ">5", ">5", "4,5",  "3,5",  "2,3",  "1,5", "1,0","0,6"],
    ["Lts, Lt2, Lt3","5", "2,8", "1,4","0,9","0,5","0,3",  "0,1",  "",     "",    "",    ""],
    ["Tu3, Tu4",    ">5","5",   "3,6","2,5","1,7","0,6",  "0,4",  "0,1",  "0,1", "",    ""],
    ["Tu2, Tl, Tt", "5", "3",   "1,3","0,5","0,3","0,2",  "0,1",  "",     "",    "",    ""],
], columns=["Bodenart","2","3","4","5","6","8","10","12","14","17","20"])

# — Spaltenbreiten in dm für die Suche —
_KAP_DMS = [2,3,4,5,6,8,10,12,14,17,20]
def kapillaraufstiegsrate(horizonte: list[dict], physiogr: float) -> float | None:
    """
    Berechnet die mittlere Kapillar-Aufstiegsrate (mm/d).
    - sucht nach dem ersten Horizont, dessen 'hz' (case-insensitive) den Substring 'gr' enthält
    """
    # 1) Gr-Horizont finden (case-insensitive)
    gr_horizont = next(
        (h for h in horizonte if isinstance(h.get("hz"), str) and "gr" in h["hz"].lower()),
        None
    )
    if gr_horizont is None:
        return None

    start_cm = gr_horizont.get("z_top")
    if start_cm is None:
        return None

    # 2) Abstand zur physiologischen Gründigkeit
    dist_cm = start_cm - physiogr
    if dist_cm <= 0:
        return 0.0

    dist_dm = dist_cm / 10

    # 3) nächstliegende dm-Spalte wählen
    dm = min(_KAP_DMS, key=lambda x: abs(x - dist_dm))

    # 4) Bodenart aus dem Gr-Horizont
    bod = str(gr_horizont.get("Bodenart", ""))
    # substring-Match in der Tabelle
    row = _KAP_TABLE[_KAP_TABLE["Bodenart"].str.lower().str.contains(bod.split()[0].lower(), na=False)]
    if row.empty:
        return None

    val = row[str(dm)].iloc[0]
    if not isinstance(val, str) or not val.strip():
        return None

    # 5) Komma → Punkt, in float
    try:
        return float(val.replace(",", "."))
    except ValueError:
        return None
# ——————————————————————————————————————————
# Hauptprogramm
# ——————————————————————————————————————————
def main():
    # 1) Pfad zur Eingabedatei
    eingabe = input("Pfad zur Eingabe-Excel-Datei: ").strip().strip('"').strip("'")
    df_in = pd.read_excel(eingabe)

    # 2) Nutzungsart abfragen
    nutzungsart = input("Nutzungsart (Acker / Grünland): ").strip().lower()
    if nutzungsart not in ("acker", "grünland", "gruenland"):
        print("Ungültige Eingabe – verwende 'acker'.")
        nutzungsart = "acker"
    if nutzungsart == "grünland":
        nutzungsart = "gruenland"

    # 3) Kalkbedarf-Tabellen laden
    kalk_df_acker = pd.read_csv("kalkbedarf_acker.csv")
    kalk_df_gruen = pd.read_csv("kalkbedarf_gruen.csv")

    # 4) Vorschau der Eingabedaten
    print("\nEingelesene Daten (Vorschau):")
    print(df_in.head(10).to_string(index=False))
    if len(df_in) > 10:
        print(f"... und noch {len(df_in) - 10} weitere Zeilen")

    # 5) Spalten finden
    cols = df_in.columns.tolist()
    def find_col(*keys):
        for c in cols:
            if all(k.lower() in c.lower() for k in keys):
                return c
        raise KeyError(f"Keine Spalte mit {keys!r} gefunden. Verfügbare: {cols}")

    col_tiefe    = find_col("tiefe")
    col_bd       = find_col("trocken", "dichte")
    col_skelett  = find_col("skelett")
    col_humus    = find_col("humus")
    col_ph       = find_col("ph")
    col_bodenart = find_col("bodenart")
    col_horizont = find_col("horizont")

    # 6) Tiefenbereich in z_top/z_bot aufsplitten
    depth_str     = df_in[col_tiefe].astype(str).str.strip()
    z_split       = depth_str.str.split("-", expand=True)
    df_in["z_top"] = pd.to_numeric(z_split[0], errors="coerce")
    df_in["z_bot"] = pd.to_numeric(z_split[1], errors="coerce")

    # 7) Dichte & Skelett in float
    for col in (col_bd, col_skelett):
        df_in[col] = pd.to_numeric(df_in[col], errors="coerce")

    # 8) Humus in numerisch (Mittelwert, <-Werte halbieren)
    def parse_range(val):
        s = str(val).strip()
        m = re.match(r'<\s*(\d+(\.\d+)?)', s)
        if m:
            return float(m.group(1)) / 2
        s = s.replace('<','').replace('>','').strip()
        if '-' in s:
            lo, hi = s.split('-', 1)
            try: return (float(lo)+float(hi))/2
            except: return None
        try: return float(s)
        except: return None

    df_in["humus_num"] = df_in[col_humus].apply(parse_range)
    df_in[col_ph]      = pd.to_numeric(df_in[col_ph], errors="coerce")

    # 9) Weitere Eingaben
    bodenform = input("Bodenform: ")
    try:
        physiogr = int(input("Physiologische Gründigkeit (cm): "))
    except ValueError:
        physiogr = 100
        print("Ungültig, verwende 100 cm als Standard.")

    # 10) Liste der Horizonte
    horizonte = []
    for _, r in df_in.iterrows():
        horizonte.append({
            "hz":       r[col_horizont],
            "z_top":    r["z_top"],
            "z_bot":    r["z_bot"],
            "bd":       r[col_bd],
            "humus":    r["humus_num"],
            "pH":       r[col_ph],
            "Bodenart": r[col_bodenart],
            "skelett":  r[col_skelett]
        })

    # 11) Oberboden–Horizont
    ober      = min(horizonte, key=lambda h: h["z_top"])
    ph_ob     = ober["pH"]
    humus_ob  = ober["humus"]
    bodentyp  = ober["Bodenart"]
    bg        = bodentyp_to_bg.get(bodentyp)

    # 12) Kalkbedarf nur einmal korrekt berechnen
    if bg is None:
        print(f"Warnung: Unbekannter Bodentyp '{bodentyp}'.")
        kalkb, msg = None, None
    else:
        kalkb, msg = berechne_kalkbedarf(
            bg, ph_ob, humus_ob,
            nutzungsart,
            kalk_df_acker,
            kalk_df_gruen
        )
        if msg:
            print("→", msg)

    # 13) Humusvorrat bis 1 m und Umrechnung in Mg/ha
    _, total_hum    = humusvorrat(horizonte, max_tiefe=100)
    total_hum_Mg_ha = total_hum * 10

    # 14) nFK bis zur physiologischen Gründigkeit
    nfk_mm = gesamt_nfk(horizonte, physiogr)

    # 15) Ergebnis-DataFrame und Ausgabe
    df_sum = pd.DataFrame([{
        "Bodentyp, Bodenform":             f"{bodentyp}, {bodenform}",
        "Physiologische Gründigkeit (cm)": physiogr,
        "Humusvorrat bis 1 m (Mg/ha)":     total_hum_Mg_ha,
        "pH Oberboden":                    ph_ob,
        "Kalkbedarf (dt CaO/ha)":          kalkb,
        "nFK (mm)":                        nfk_mm
    }])
    print("\nErgebnisse:")
    print(df_sum.to_string(index=False))

    # 16) Speichern
    out = input("Dateiname für Ausgabedatei (z.B. output.xlsx): ").strip()
    if not out.lower().endswith(('.xls','.xlsx')):
        out += '.xlsx'
    df_sum.to_excel(out, index=False)
    print(f"→ '{out}' wurde erzeugt.")

if __name__ == "__main__":
    main()

    # ——— Debug für Kalkbedarf ———
    import pandas as pd
    from bodenauswertung import build_horizonte_list, bodentyp_to_bg, humuskategorie, berechne_kalkbedarf

    # 1) Lies dieselbe Eingabedatei nochmal ein (oder gib hier den Pfad hartkodiert an)
    df = pd.read_excel("Pfad/zu/deiner_Eingabe.xlsx")

    # 2) Baue die Horizonte-Liste
    horizonte = build_horizonte_list(df)

    # 3) Nimm den obersten Horizont
    ober = min(horizonte, key=lambda h: h["z_top"])

    # 4) Ermittle bg, humus-Kategorie und pH
    bodenart     = ober["Bodenart"].strip()
    bg           = bodentyp_to_bg.get(bodenart)
    ph_wert      = ober["pH"]
    humus_wert   = ober["humus"]
    humus_kat    = humuskategorie(humus_wert)

    print("DEBUG: bg=", bg)
    print("DEBUG: Bodenart =>", repr(bodenart))
    print("DEBUG: pH =", ph_wert)
    print("DEBUG: humus =", humus_wert, "=> kat", humus_kat)

    # 5) Schau dir die Tabellen-Spalten an
    df_acker = pd.read_csv("kalkbedarf_acker.csv")
    print("DEBUG: Verfügbare Humuskategorien in CSV:", df_acker["humus_kat"].unique())

    # 6) Suche simulieren und Ergebnis zeigen
    kalk, msg = berechne_kalkbedarf(
        bg, ph_wert, humus_wert, "acker",
        df_acker, pd.read_csv("kalkbedarf_gruen.csv")
    )
    print("DEBUG: berechne_kalkbedarf ->", kalk, msg)
