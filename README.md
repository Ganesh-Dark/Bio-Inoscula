# Bio-Inoscula

Bio-Inoscula is a ReAct-powered biomedical AI agent. It acts as a central hub, dynamically querying and integrating biological data from NCBI, KEGG, Reactome, ClinVar, and Rhea. Users can submit natural language queries regarding genes, metabolic pathways, diseases, chemical compounds, approved drugs, and genomic mutations to retrieve factual, cross-referenced answers directly from official biological databases.

> **[IMPORTANT OVERVIEW DISCLAIMER]**
> **Bio-Inoscula is designed as an "Overview Agent." Because biological databases are vast (pathways can contain hundreds of genes and metabolites), query outputs are paginated and filtered to optimize context utilization and prevent memory issues.**
> **For exhaustive, raw-scale datasets, query parameters can be adjusted directly in the analytics modules.**

---

## Features & Capabilities

- **Pathways & Metabolism (KEGG & Reactome):** Fetches genes, compounds, and reactions involved in specific biological pathways. Merges and deduplicates datasets across databases.
- **Rhea Universal Reaction Mapping:** High-speed offline mapping between KEGG Reactions, Reactome Reactions, and Rhea Master IDs. Enriches reactions with full balanced equations, EC numbers, and UniProt cross-references.
- **Sub-Second Rhea Caching:** Pre-compiled binary cache (`Rhea_files/rhea_db.pkl`) loads over 18,000 Rhea master reactions and 250,000 reverse lookups in under 0.1 seconds.
- **Diseases & Phenotypes (KEGG Disease & Wikipedia):** Identifies genes and pathways linked to human diseases in KEGG Disease, with automated Wikipedia fallback for rare conditions.
- **Clinical Variants (ClinVar):** Leverages an embedded DuckDB engine to execute fast queries against NCBI ClinVar for pathogenic mutations and associated clinical phenotypes.
- **Gene Summaries (NCBI HGNC):** Retrieves official gene nomenclature, summaries, and genomic positions directly from NCBI.
- **Local Enzyme & Reaction Analytics:** Offline parsing of KEGG Reactions, Enzymes, Modules, and Orthology (KO) to identify isozymes, orphan reactions, and shared metabolites without rate limits.
- **Chemical Structure Resolution:** Resolves common chemical and drug names through PubChem to standard InChIKeys and maps them across KEGG, ChEBI, HMDB, and DrugBank.
- **Persistent Conversation Memory:** SQLite-backed episodic memory (`bioweaver_memory.db`) preserves conversational context and message history across turns and server restarts.
- **Intelligent Query Routing:** ReAct agent routes theoretical textbook questions to internal knowledge while reserving database tools for empirical and clinical queries.

---

## Setup Instructions

### Prerequisites & Python Environment

Activate your Python environment:
```bash
conda activate python_env
```
Or use the `uv` virtual environment workflow:
```bash
uv venv
source .venv/bin/activate
```

### Data Files Setup

Most required database files (HGNC, KEGG Pathways, KEGG Diseases, KEGG Organisms, Reactome, and Rhea TSVs) are included in this repository.

1. **ClinVar Database:**
   The ClinVar database file (`variant_summary.txt.gz`) exceeds GitHub file size limits and must be downloaded locally:
   ```bash
   python setup_dbs.py
   ```
   *This downloads the latest ClinVar summary directly from the NCBI FTP server.*

2. **Rhea Pickle Cache Generation (Optional if rebuilding):**
   To recompile the fast binary Rhea database from source TSVs:
   ```bash
   python scripts/build_rhea_pickle.py
   ```
   *Generates `Rhea_files/rhea_db.pkl` for sub-second reaction mapping.*

### API Key Configuration

Bio-Inoscula supports Google Gemini, Groq, or Hugging Face LLM backends:

1. Create a `.env` file in the root directory:
   ```bash
   cp .env.example .env
   ```
2. Configure your API key in `.env`:
   ```env
   LLM_API=your_actual_api_key_here
   ```

---

## Running the Application

### Using `uv` (Recommended)
```bash
uv run app.py
```

### Using Standard Python
```bash
python app.py
```

The application server will start at:
**http://localhost:8000**

Open your web browser and navigate to `http://localhost:8000` to access the chat dashboard.

---

## Example Queries

### Pathway & Metabolism
- "List all the genes, compounds, and drugs involved in carbohydrate metabolism."
- "I want to know the genes in the TCA cycle. I only want data from Reactome."
- "What compounds are created during glycolysis?"
- "Show me the difference between KEGG and Reactome data for the pentose phosphate pathway."

### Rhea Reaction Mapping
- "Get tyrosine metabolism reactions from KEGG along with Rhea IDs."
- "Map glycolysis reactions to Rhea and show their chemical equations."
- "Find Rhea reactions catalyzed by EC 1.1.1.1."
- "What is Rhea 10012?"

### Disease & Clinical Queries
- "Search for Parkinson's disease. Get me the overview and find all linked genes from KEGG."
- "What genes are associated with Alzheimer's disease in the KEGG database?"
- "Tell me about Glioblastoma and list any related metabolic pathways."
- "What does the KEGG database say about Type 2 Diabetes?"

### Gene Deep-Dives & Mutations
- "Tell me everything you know about the BRCA1 gene. What is its official NCBI summary?"
- "Look up the TP53 gene. What diseases is it linked to in KEGG?"
- "What are the most dangerous pathogenic mutations for the TP53 gene in ClinVar?"
- "Find the top pathogenic variants for BRCA1 in ClinVar."

### Chemical & Enzyme Analytics
- "Find all reactions where pyruvate is a product."
- "What are the substrates and products of reaction R00224?"
- "Which enzymes in Glycolysis are oxidoreductases?"
- "Resolve 'pyruvate' and give me all its database cross-reference IDs."

---

## Data Acknowledgments & Credits

Bio-Inoscula integrates data from the following public biomedical repositories:

- **KEGG (Kyoto Encyclopedia of Genes and Genomes):** Pathway, disease, reaction, and enzyme data. KEGG is freely available for academic use (commercial use requires a license from Kanehisa Laboratories).
- **Rhea:** Biochemical reaction data sourced from Rhea, developed by the Swiss Institute of Bioinformatics (SIB).
- **NCBI / NLM:** Gene nomenclature, genomic summaries, and ClinVar variant records sourced from the National Center for Biotechnology Information.
- **Reactome:** Open-source curated biological pathway data provided by the Reactome knowledgebase.
- **PubChem:** Chemical structure mapping, InChIKey derivation, and compound cross-references provided by NCBI PubChem.
- **HGNC:** Standardized human gene nomenclature provided by the HUGO Gene Nomenclature Committee.
