"""
Stranica 5: Kvote sa Screenshota
Upload screenshota kvota kladionice (npr. SuperSport) za turnire koje The Odds API
ne pokriva (ATP 250/500). Claude vision izvuče parove i kvote, korisnik potvrdi,
pa se spreme u Supabase — daily ticket pipeline ih automatski povlači i mergira
s Odds API rezultatima.

RUNDA (26.09.2026 17:04): korisnik je od danas upisuje ovdje, za svaki par, u trenutku
uploada. Pipeline vise NIKAD ne pogadja rundu — cita je iskljucivo iz ovog zapisa
(`round` unutar svakog para u `screenshot_odds.odds_data`). Zasto: vidi blok
"RUNDA SE UNOSI RUCNO" u `utils/helpers.py`.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import datetime
import pandas as pd
import streamlit as st
from database import supabase_client as db
from agent.data_fetcher import extract_odds_from_screenshot
from utils.helpers import (today_zagreb, tomorrow_zagreb, format_date, format_date_hr,
                           ROUND_CHOICES, ROUND_LABEL_HR, ROUND_CODE_BY_LABEL,
                           normalize_round_code)

st.set_page_config(page_title="Kvote sa Screenshota | Tennis Agent", page_icon="📸", layout="wide")
st.title("📸 Kvote sa Screenshota")

st.markdown(
    "Uploadaj screenshot kvota kladionice za **službeni turnir** — "
    "**bez kvalifikacijskih mečeva**. Claude će pročitati parove i kvote, "
    "ti ih provjeriš i **upišeš rundu**, pa se spreme za daily ticket."
)

_PLACEHOLDER = "— odaberi rundu —"
_ROUND_LABELS = [label for _, label in ROUND_CHOICES]


def _apply_bulk(scope: str) -> None:
    """Padajuci izbornik "za sve parove": prepisuje rundu SVIH parova i iznova
    postavlja tablicu (nova verzija kljuca), pa pojedinacne izmjene nakon toga
    krecu od te vrijednosti."""
    code = ROUND_CODE_BY_LABEL.get(st.session_state.get(f"bulk_{scope}"))
    if not code:
        return
    base = st.session_state.get(f"rb_{scope}") or {}
    st.session_state[f"rb_{scope}"] = {k: code for k in base}
    st.session_state[f"rv_{scope}"] = st.session_state.get(f"rv_{scope}", 0) + 1


def _round_editor(scope: str, entries: dict) -> dict:
    """Tablica parova s rundom koja se moze mijenjati po paru. Vraca {kljuc_para: kod}
    ('' gdje runda nije odabrana). Pocetna vrijednost je ono sto je vec zapisano uz par."""
    st.session_state.setdefault(f"rv_{scope}", 0)
    base = st.session_state.get(f"rb_{scope}")
    if base is None or set(base) != set(entries):
        base = {k: normalize_round_code(v.get("round")) for k, v in entries.items()}
        st.session_state[f"rb_{scope}"] = base

    st.selectbox(
        "Runda za **sve** parove odjednom (pojedinačni par ispraviš u tablici ispod)",
        [_PLACEHOLDER] + _ROUND_LABELS, key=f"bulk_{scope}",
        on_change=_apply_bulk, args=(scope,),
    )

    keys = list(entries)
    frame = pd.DataFrame(
        {
            "Vrijeme": [entries[k].get("start_time") or "—" for k in keys],
            "Igrač 1": [entries[k].get("p1", "") for k in keys],
            "Kvota 1": [entries[k].get("p1_odds") for k in keys],
            "Igrač 2": [entries[k].get("p2", "") for k in keys],
            "Kvota 2": [entries[k].get("p2_odds") for k in keys],
            "Runda": [ROUND_LABEL_HR.get(base.get(k, ""), None) for k in keys],
        },
        index=keys,
    )
    edited = st.data_editor(
        frame,
        key=f"editor_{scope}_{st.session_state[f'rv_{scope}']}",
        hide_index=True,
        width="stretch",
        disabled=["Vrijeme", "Igrač 1", "Kvota 1", "Igrač 2", "Kvota 2"],
        column_config={
            "Runda": st.column_config.SelectboxColumn(
                "Runda", options=_ROUND_LABELS, required=True,
                help="Runda kako je vidiš na kladionici. Ako se isti dan igraju dvije "
                     "runde (npr. zadnji mečevi 1/4 i prvo polufinale), ispravi par po par."),
        },
    )
    return {k: ROUND_CODE_BY_LABEL.get(edited.loc[k, "Runda"], "") for k in keys}


today = today_zagreb()
tomorrow = tomorrow_zagreb()
date_options = {
    f"Danas — {format_date_hr(today)}": format_date(today),
    f"Sutra — {format_date_hr(tomorrow)}": format_date(tomorrow),
}
date_label = st.radio("Za koji dan su ove kvote?", list(date_options.keys()), horizontal=True)
match_date = date_options[date_label]

uploaded = st.file_uploader("Screenshot kvota (PNG/JPG)", type=["png", "jpg", "jpeg"])

if uploaded is not None:
    st.image(uploaded, caption="Učitani screenshot", width=500)

    if st.button("🔍 Pročitaj kvote sa slike", type="primary"):
        media_type = uploaded.type or "image/png"
        with st.spinner("Claude čita kvote sa screenshota..."):
            extracted = extract_odds_from_screenshot(uploaded.getvalue(), media_type=media_type)
        st.session_state["extracted_odds"] = extracted
        st.session_state["extracted_for_date"] = match_date
        # Novo citanje = nova tablica rundi (stari odabir ne smije procuriti na nove parove).
        st.session_state.pop("rb_new", None)
        st.session_state.pop("bulk_new", None)
        st.session_state["rv_new"] = st.session_state.get("rv_new", 0) + 1

extracted = st.session_state.get("extracted_odds")
extracted_for = st.session_state.get("extracted_for_date")

if extracted is not None and extracted_for == match_date:
    if not extracted:
        st.warning("Nisam uspio pročitati nijedan par sa slike. Pokušaj s jasnijim screenshotom.")
    else:
        st.subheader(f"Pronađeno {len(extracted)} parova — provjeri i upiši rundu")
        rounds = _round_editor("new", extracted)
        _missing = [k for k, code in rounds.items() if not code]

        _n_time = sum(1 for v in extracted.values() if v.get("start_time"))
        if _n_time:
            st.success(
                f"Vrijeme početka pročitano za {_n_time}/{len(extracted)} parova — to je "
                "zagrebačko vrijeme s kladionice i **ima prioritet nad API-jem**, koji za "
                "neke turnire kasni po nekoliko sati. Utječe na oznaku dan/noć i na to za "
                "koji se sat dohvaća vremenska prognoza."
            )
        else:
            st.warning(
                "Vrijeme početka nije pročitano ni za jedan par — pipeline će pasti na "
                "API-jev sat, koji zna kasniti (za Montreal ~3h). Ako se na screenshotu "
                "vrijeme vidi, probaj snimku na kojoj je stupac s vremenom jasno čitljiv."
            )

        st.caption(
            "Ako nešto nije točno pročitano, otkaži i probaj ponovno s drugačijim screenshotom — "
            "ručno se mijenja samo runda."
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Spremi ove kvote", type="primary"):
                if _missing:
                    st.error(f"Runda nije upisana za {len(_missing)} od {len(rounds)} parova. "
                             "Odaberi je gore za sve parove ili u tablici po paru — "
                             "pipeline je više ne pogađa sam.")
                else:
                    to_save = {k: {**v, "round": rounds[k]} for k, v in extracted.items()}
                    db.save_screenshot_odds(match_date, to_save)
                    st.success(f"Spremljeno {len(to_save)} parova za {match_date}. "
                               "Daily ticket pipeline će ih sada koristiti.")
                    del st.session_state["extracted_odds"]
                    del st.session_state["extracted_for_date"]
                    st.session_state.pop("rb_new", None)
                    st.rerun()
        with col2:
            if st.button("❌ Odustani"):
                del st.session_state["extracted_odds"]
                del st.session_state["extracted_for_date"]
                st.session_state.pop("rb_new", None)
                st.rerun()

st.markdown("---")
st.subheader("Već spremljene kvote")
for label, d in date_options.items():
    saved = db.get_screenshot_odds(d)
    _no_round = sum(1 for v in saved.values() if not normalize_round_code(v.get("round")))
    _flag = f" — ⚠️ {_no_round} bez runde" if _no_round else ""
    with st.expander(f"{label} — {len(saved)} parova{_flag}", expanded=bool(_no_round)):
        if saved:
            if _no_round:
                st.warning(
                    f"{_no_round} parova nema upisanu rundu (spremljeni prije 26.09.2026 ili "
                    "bez odabira). Pipeline takve mečeve i dalje analizira, ali model tada "
                    "vidi 'runda nije upisana' umjesto runde. Upiši je ovdje i spremi."
                )
            saved_rounds = _round_editor(f"saved_{d}", saved)
            _old = sum(1 for v in saved.values() if not v.get("start_time"))
            if _old:
                st.info(
                    f"{_old} parova nema vrijeme početka — spremljeni su prije 04.08.2026., "
                    "kad se vrijeme još nije čitalo sa screenshota. Ponovni upload iste "
                    "snimke ih nadopisuje s vremenom (spremanje se mergea, ništa se ne gubi)."
                )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("💾 Spremi runde", key=f"save_rounds_{d}"):
                    updated = {k: {**v, "round": saved_rounds.get(k, "")} for k, v in saved.items()}
                    db.save_screenshot_odds(d, updated)
                    st.session_state.pop(f"rb_saved_{d}", None)
                    st.session_state[f"rv_saved_{d}"] = st.session_state.get(f"rv_saved_{d}", 0) + 1
                    st.success("Runde spremljene.")
                    st.rerun()
            with c2:
                if st.button("🗑️ Obriši sve", key=f"delete_{d}"):
                    db.delete_screenshot_odds(d)
                    st.success(f"Obrisane sve kvote za {label.split('—')[1].strip()}.")
                    st.rerun()
        else:
            st.caption("Nema spremljenih kvota za ovaj dan.")
