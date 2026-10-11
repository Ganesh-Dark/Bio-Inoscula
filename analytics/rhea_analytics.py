import os
import pickle
import difflib
import pandas as pd
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RHEA_DIR = os.path.join(BASE_DIR, "..", "Rhea_files")
KEGG_DIR = os.path.join(BASE_DIR, "..", "Kegg_files")

FILE_ALL = os.path.join(RHEA_DIR, "rhea_all_reactions.tsv")
FILE_KEGG = os.path.join(RHEA_DIR, "rhea2kegg_reaction.tsv")
FILE_REACTOME = os.path.join(RHEA_DIR, "rhea2reactome.tsv")
FILE_UNIPROT = os.path.join(RHEA_DIR, "rhea2uniprot_sprot.tsv")
FILE_EC = os.path.join(RHEA_DIR, "rhea2ec.tsv")
FILE_KEGG_ENZYME = os.path.join(KEGG_DIR, "enzyme.tsv")
FILE_CACHE = os.path.join(RHEA_DIR, "rhea_db.pkl")

_DB = None

def _load_all():
    # Pre-loads the Rhea database into memory from binary cache or raw TSVs
    global _DB
    if _DB is not None:
        return

    if os.path.exists(FILE_CACHE):
        print(f"\n[Rhea Analytics] Loading pre-compiled binary cache from: {FILE_CACHE}")
        with open(FILE_CACHE, "rb") as f:
            _DB = pickle.load(f)
        print(f"[Rhea Analytics] Cache loaded instantly: {len(_DB['rhea_details'])} Master Rhea reactions.")
        return

    print("\n[Rhea Analytics] Pre-loading local Rhea mapping files into memory...")
    _DB = {
        "rhea_to_kegg": {},
        "rhea_to_reactome": {},
        "rhea_to_uniprot": {},
        "rhea_to_ec": {},
        "rhea_details": {},
        "reverse_lookup": {} # Maps any external ID to a set of Rhea Master IDs
    }

    # Helper to load mapping TSVs using pandas
    def load_mapping(filepath, target_dict):
        if not os.path.exists(filepath):
            return
        df = pd.read_csv(filepath, sep='\t', dtype=str).fillna("")
        cols = df.columns
        if len(cols) >= 4:
            master_col = cols[2]
            ext_col = cols[3]
            for _, row in df.iterrows():
                master_id = str(row[master_col]).strip()
                ext_id = str(row[ext_col]).strip()
                if not master_id or not ext_id:
                    continue
                if master_id not in target_dict:
                    target_dict[master_id] = set()
                target_dict[master_id].add(ext_id)

                if ext_id not in _DB["reverse_lookup"]:
                    _DB["reverse_lookup"][ext_id] = set()
                _DB["reverse_lookup"][ext_id].add(master_id)

    load_mapping(FILE_KEGG, _DB["rhea_to_kegg"])
    load_mapping(FILE_REACTOME, _DB["rhea_to_reactome"])
    load_mapping(FILE_UNIPROT, _DB["rhea_to_uniprot"])
    load_mapping(FILE_EC, _DB["rhea_to_ec"])

    # Load details
    if os.path.exists(FILE_ALL):
        df_all = pd.read_csv(FILE_ALL, sep='\t', dtype=str).fillna("")
        for _, row in df_all.iterrows():
            rhea_full = str(row.iloc[0]).strip()
            master_id = rhea_full.replace("RHEA:", "").strip()
            eq = str(row.iloc[1]).strip() if len(row) > 1 else ""
            chebi = str(row.iloc[2]).strip() if len(row) > 2 else ""
            ec = str(row.iloc[3]).strip() if len(row) > 3 else ""
            enzymes = str(row.iloc[4]).strip() if len(row) > 4 else "0"

            _DB["rhea_details"][master_id] = {
                "equation": eq,
                "chebi_ids": chebi.split(";") if chebi else [],
                "ec_numbers": ec,
                "enzyme_count": enzymes
            }
    print(f"[Rhea Analytics] Database loaded: {len(_DB['rhea_details'])} Master Rhea reactions.")

def format_rhea_id(rhea_id):
    # rhea_id: Raw string of Rhea identifier, with or without 'RHEA:' prefix
    return str(rhea_id).upper().replace("RHEA:", "").strip()

def get_rhea_comprehensive(rhea_id):
    # rhea_id: Numeric or prefixed Rhea identifier (e.g. '17825' or 'RHEA:17825')
    print(f"\n[Rhea Analytics] Fetching comprehensive details for: {rhea_id}")
    _load_all()
    master_id = format_rhea_id(rhea_id)
    if master_id not in _DB["rhea_details"]:
        return {"error": f"Rhea ID {rhea_id} not found."}

    details = _DB["rhea_details"][master_id].copy()
    details["rhea_id"] = f"RHEA:{master_id}"

    # Add cross references
    details["mapped_kegg_ids"] = list(_DB["rhea_to_kegg"].get(master_id, []))
    details["mapped_reactome_ids"] = list(_DB["rhea_to_reactome"].get(master_id, []))
    details["mapped_uniprot_ids"] = list(_DB["rhea_to_uniprot"].get(master_id, []))
    details["mapped_ec_numbers"] = list(_DB["rhea_to_ec"].get(master_id, []))

    return details

def reverse_lookup(external_id):
    # external_id: External identifier from EC (e.g. '2.7.1.1'), KEGG (e.g. 'R00299'), Reactome, or UniProt
    print(f"\n[Rhea Analytics] Reverse lookup for external ID: '{external_id}'")
    _load_all()
    raw_id = str(external_id).strip()
    clean_id = raw_id
    if clean_id.upper().startswith("EC:"):
        clean_id = clean_id[3:].strip()

    matches = _DB["reverse_lookup"].get(clean_id, set())
    if not matches:
        matches = _DB["reverse_lookup"].get(raw_id, set())

    results = []
    # Local lookup success
    if matches:
        for m in matches:
            eq = _DB["rhea_details"].get(m, {}).get("equation", "Unknown Equation")
            results.append({"rhea_id": f"RHEA:{m}", "equation": eq, "source": "Local TSV Database"})
        print(f"[Rhea Analytics] Found {len(results)} local matches for '{external_id}'")
        return {"external_id": external_id, "matched_rhea_reactions": results}

    # API Fallback
    print(f"[Rhea Analytics] '{external_id}' not found locally. Falling back to Rhea REST API...")
    api_url = f"https://www.rhea-db.org/rhea?query={external_id}&columns=rhea-id,equation&format=tsv"
    res = requests.get(api_url, timeout=10)
    if res.status_code == 200 and res.text.strip():
        lines = res.text.strip().split("\n")
        if len(lines) > 1:
            for line in lines[1:]:
                if not line.strip():
                    continue
                parts = line.split("\t")
                if len(parts) >= 2:
                    rhea_id = parts[0]
                    equation = parts[1] if len(parts) > 1 else ""
                    results.append({"rhea_id": rhea_id, "equation": equation, "source": "Rhea REST API Fallback"})

    if not results:
        print(f"[Rhea Analytics] No matches found for '{external_id}'")
        return {"error": f"No Rhea mappings found for ID '{external_id}' neither locally nor via API."}

    return {"external_id": external_id, "matched_rhea_reactions": results}

def search_rhea_by_text(query):
    # query: Search string representing enzyme name, EC number, chemical compound, or reaction equation
    print(f"\n[Rhea Analytics] Searching Rhea reactions for: '{query}'")
    _load_all()
    q = str(query).strip().lower()
    clean_ec = q[3:].strip() if q.startswith("ec:") else q

    matches = []
    seen_ids = set()

    # 1. Search directly in equation text or EC numbers in Rhea details
    for master_id, details in _DB["rhea_details"].items():
        eq = details.get("equation", "").lower()
        ec = details.get("ec_numbers", "").lower()
        if q in eq or clean_ec in ec:
            seen_ids.add(master_id)
            matches.append({
                "rhea_id": f"RHEA:{master_id}",
                "equation": details.get("equation", ""),
                "ec_numbers": details.get("ec_numbers", "")
            })
            if len(matches) >= 10:
                break

    # 2. If no direct matches and query might be an enzyme name (e.g. 'hexokinase'), check enzyme mapping
    if len(matches) == 0 and os.path.exists(FILE_KEGG_ENZYME):
        print(f"[Rhea Analytics] Checking enzyme name mapping in enzyme.tsv for: '{query}'")
        df_enz = pd.read_csv(FILE_KEGG_ENZYME, sep="\t", header=None, names=["ec", "names"]).fillna("")
        matched_ecs = df_enz[df_enz["names"].str.lower().str.contains(q, regex=False)]["ec"].tolist()
        for matched_ec in matched_ecs[:5]:
            ec_clean = str(matched_ec).strip()
            ec_matches = _DB["reverse_lookup"].get(ec_clean, set())
            for m in ec_matches:
                if m not in seen_ids:
                    seen_ids.add(m)
                    eq = _DB["rhea_details"].get(m, {}).get("equation", "Unknown Equation")
                    ec_val = _DB["rhea_details"].get(m, {}).get("ec_numbers", ec_clean)
                    matches.append({
                        "rhea_id": f"RHEA:{m}",
                        "equation": eq,
                        "ec_numbers": ec_val
                    })
                    if len(matches) >= 10:
                        break

    print(f"[Rhea Analytics] Search completed. Found {len(matches)} results.")
    if not matches:
        return {"error": f"No Rhea reactions found matching '{query}'."}

    return {"query": query, "total_matches": len(matches), "matches": matches}

def find_rhea_by_chebi(chebi_id):
    # chebi_id: ChEBI identifier such as 'CHEBI:15378' or numeric '15378'
    print(f"\n[Rhea Analytics] Finding Rhea reactions for ChEBI ID: {chebi_id}")
    _load_all()
    c_id = chebi_id.upper().strip()
    if not c_id.startswith("CHEBI:"):
        c_id = f"CHEBI:{c_id}"

    matches = []
    for master_id, details in _DB["rhea_details"].items():
        if c_id in details["chebi_ids"]:
            matches.append({
                "rhea_id": f"RHEA:{master_id}",
                "equation": details["equation"]
            })

    if not matches:
        print(f"[Rhea Analytics] No reactions found for ChEBI ID {c_id}")
        return {"error": f"No Rhea reactions found using {c_id}."}

    print(f"[Rhea Analytics] Found {len(matches)} reactions involving ChEBI ID {c_id}")
    return {"chebi_id": c_id, "total_reactions": len(matches), "reactions": matches[:50]}

def _resolve_kegg_pathway_id(identifier):
    # identifier: String representing a pathway ID (e.g. 'map00010', '00010') or name (e.g. 'tyrosine metabolism')
    raw = str(identifier).strip()
    if raw.lower().startswith("map") and raw[3:].isdigit():
        return raw.lower(), None
    if raw.lower().startswith("ko") and raw[2:].isdigit():
        return f"map{raw[2:]}", None
    if raw.isdigit():
        return f"map{raw.zfill(5)}", None

    pathway_file = os.path.join(KEGG_DIR, "kegg_pathways.tsv")
    if not os.path.exists(pathway_file):
        print(f"[Rhea Analytics] Warning: kegg_pathways.tsv not found at {pathway_file}")
        return None, None

    df_paths = pd.read_csv(pathway_file, sep="\t", header=None, names=["map_id", "name"]).fillna("")
    q = raw.lower().strip()

    # 1. Exact match (case-insensitive)
    exact = df_paths[df_paths["name"].str.lower() == q]
    if not exact.empty:
        row = exact.iloc[0]
        return row["map_id"], row["name"]

    # 2. Substring match (e.g. 'tyrosine' inside 'Tyrosine metabolism')
    sub = df_paths[df_paths["name"].str.lower().str.contains(q, regex=False)]
    if not sub.empty:
        row = sub.iloc[0]
        return row["map_id"], row["name"]

    # 3. Clean common noise words like 'pathway' or 'metabolism'
    cleaned_q = q.replace("pathway", "").replace("metabolism", "").strip()
    if cleaned_q and cleaned_q != q:
        root_match = df_paths[df_paths["name"].str.lower().str.contains(cleaned_q, regex=False)]
        if not root_match.empty:
            row = root_match.iloc[0]
            return row["map_id"], row["name"]

    # 4. Fuzzy typo matching using Python difflib
    names_list = df_paths["name"].tolist()
    close_matches = difflib.get_close_matches(raw, names_list, n=1, cutoff=0.55)
    if not close_matches and cleaned_q:
        close_matches = difflib.get_close_matches(cleaned_q, names_list, n=1, cutoff=0.50)

    if close_matches:
        matched_name = close_matches[0]
        matched_row = df_paths[df_paths["name"] == matched_name].iloc[0]
        return matched_row["map_id"], matched_row["name"]

    return None, None

def get_pathway_rhea_mapping(kegg_pathway_id):
    # kegg_pathway_id: String representing KEGG pathway identifier (e.g. 'map00010') or pathway name (e.g. 'tyrosine metabolism')
    print(f"\n[Rhea Analytics] Fetching Rhea mapping for pathway: '{kegg_pathway_id}'")
    _load_all()

    resolved_id, resolved_name = _resolve_kegg_pathway_id(kegg_pathway_id)
    if not resolved_id:
        print(f"[Rhea Analytics] Could not resolve '{kegg_pathway_id}' to a known KEGG pathway.")
        return {"error": f"Could not resolve '{kegg_pathway_id}' to a known KEGG pathway ID. Please verify the pathway name or provide its ID (e.g. 'map00350')."}

    if resolved_name:
        print(f"[Rhea Analytics] Resolved pathway '{kegg_pathway_id}' -> '{resolved_name}' ({resolved_id})")

    kegg_link_url = f"https://rest.kegg.jp/link/rn/{resolved_id}"
    kegg_rn_ids = []
    res = requests.get(kegg_link_url, timeout=15)
    if res.status_code == 200 and res.text.strip():
        for line in res.text.strip().split("\n"):
            parts = line.split("\t")
            if len(parts) == 2:
                kegg_rn_ids.append(parts[1].replace("rn:", "").strip())

    if not kegg_rn_ids:
        print(f"[Rhea Analytics] No KEGG reactions found for {resolved_id}")
        return {"error": f"No KEGG reactions found for {resolved_id}"}

    results = []
    mapped_count = 0
    for rn in kegg_rn_ids:
        rhea_ids = list(_DB["reverse_lookup"].get(rn, []))
        if rhea_ids:
            mapped_count += 1
            for r_id in rhea_ids:
                details = _DB["rhea_details"].get(r_id, {})
                uniprots = list(_DB["rhea_to_uniprot"].get(r_id, []))
                results.append({
                    "kegg_reaction": rn,
                    "rhea_master_id": f"RHEA:{r_id}",
                    "equation": details.get("equation", "N/A"),
                    "ec_numbers": details.get("ec_numbers", ""),
                    "uniprot_ids": uniprots[:5]
                })
        else:
            results.append({
                "kegg_reaction": rn,
                "rhea_master_id": None,
                "equation": "Unmapped in Rhea",
                "ec_numbers": "",
                "uniprot_ids": []
            })

    print(f"[Rhea Analytics] Successfully mapped {mapped_count}/{len(kegg_rn_ids)} reactions in {resolved_id} to Rhea.")
    return {
        "kegg_pathway_id": resolved_id,
        "pathway_name": resolved_name if resolved_name else resolved_id,
        "total_kegg_reactions": len(kegg_rn_ids),
        "mapped_to_rhea_count": mapped_count,
        "reactions": results
    }

# =====================================================================================
# OVERALL SCRIPT LOGIC EXPLANATION
# =====================================================================================
# 1. FILE STRUCTURE & CACHING:
#    The script reads 5 Rhea TSV files from Rhea_files/ and KEGG's enzyme.tsv from Kegg_files/.
#    If rhea_db.pkl exists, it loads the entire pre-compiled database in under 0.2 seconds.
# 2. DATA DICTIONARIES (_DB):
#    - rhea_to_kegg, rhea_to_reactome, rhea_to_uniprot, rhea_to_ec: Maps Rhea Master ID to external IDs.
#    - rhea_details: Maps Rhea Master ID to full equation, ChEBI participants, EC numbers, and enzyme count.
#    - reverse_lookup: Inverted index mapping any external ID (EC, KEGG, Reactome, UniProt) back to Rhea Master IDs.
# 3. PUBLIC FUNCTIONS:
#    - get_rhea_comprehensive(rhea_id): Full cross-reference dump for a specific Rhea reaction.
#    - reverse_lookup(external_id): Resolves any external ID to its universal Rhea Master ID.
#    - search_rhea_by_text(query): Searches Rhea reactions by chemical equation, EC number, or enzyme name.
#    - find_rhea_by_chebi(chebi_id): Finds all Rhea reactions consuming or producing a specific ChEBI molecule.
#    - get_pathway_rhea_mapping(kegg_pathway_id): Maps all reactions in a KEGG pathway to Rhea Master IDs
#      with their full chemical equations and associated UniProt identifiers.
# =====================================================================================

